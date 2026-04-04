import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import Skill

logger = logging.getLogger(__name__)


class SkillService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_skills(filters=None, page=1, page_size=20):
        """
        List the skills.
        Supports filters: search, is_active
        """
        VALID_ORDER_FIELDS = {'skill', 'is_active'}
        qs = Skill.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(skill__icontains=s_term) | qs.filter(description__icontains=s_term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = SkillService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'skill'
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)

        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    def list_stats(fields=None):
        """
        List the statistics of the skills.
        Supports filters: fields
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = Skill.objects.all()
        result = {}

        if wants("total_skills"):
            result["total_skills"] = qs.count()
        if wants("active_skills"):
            result["active_skills"] = qs.filter(is_active=True).count()
        if wants("inactive_skills"):
            result["inactive_skills"] = qs.filter(is_active=False).count()
        if wants("unassigned_skills"):
            from apps.team_members.models import TeamMember
            assigned_skill_ids = (
                TeamMember.objects
                .filter(is_active=True, skills__isnull=False)
                .values_list('skills', flat=True)
                .distinct()
            )
            result["unassigned_skills"] = (
                qs.filter(is_active=True)
                .exclude(pk__in=assigned_skill_ids)
                .count()
            )

        return result

    @staticmethod
    def list_options(fields=None):
        """
        List the options available for fields of skills.
        Supports filters: fields
        """

        def wants(field):
            return fields is None or field in fields

        ds = {
            "is_active": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]
        }
        result = {}

        if wants("is_active"):
            result["is_active"] = ds["is_active"]

        return result

    @staticmethod
    def get_skill(skill_id: int):
        """
        Returns the details of the specified skill id.
        """
        if not skill_id:
            raise ValidationError("Invalid: skill_id must be an integer and greater than 0.")

        skill = Skill.objects.get(pk=skill_id)

        from apps.team_members.models import TeamMember
        members = TeamMember.objects.filter(skills=skill)
        skill.total_members = members.count()
        skill.active_members = members.filter(is_active=True).count()
        skill.inactive_members = members.filter(is_active=False).count()

        return skill

    @staticmethod
    @transaction.atomic
    def create_skill(data: dict):
        """
        Creates a new skill.
        """
        if not isinstance(data, dict) or 'skill' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'skill' is a required field.")

        skill_code = data['skill'].strip().upper()
        if not skill_code:
            raise ValidationError("Invalid: skill cannot be blank.")

        # Verify whether skill already exists
        if Skill.objects.filter(skill=skill_code).exists():
            raise ValidationError(f"Skill '{skill_code}' already exists.")

        # Create the skill
        try:
            skill = Skill(
                skill=skill_code,
                description=data.get('description', '').strip(),
                is_active=data.get('is_active', True),
            )
            skill.full_clean()
            skill.save()
            return skill
        except IntegrityError as e:
            logger.error("Database error when creating skill '%s': %s", skill_code, e)
            raise ValidationError(f"Skill '{skill_code}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating skill '%s': %s", skill_code, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating skill '%s': %s", skill_code, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_skill(skill_id: int, data: dict):
        """
        Updates the specified skill id.
        """
        if not skill_id:
            raise ValidationError("Invalid: skill_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        skill = Skill.objects.get(pk=skill_id)
        if not skill:
            raise ValidationError(f"Skill '{skill_id}' does not exist.")

        if 'skill' in data:
            new_code = data['skill'].strip().upper()
            if not new_code:
                raise ValidationError("Invalid: skill cannot be blank.")
            if Skill.objects.filter(skill=new_code).exclude(pk=skill_id).exists():
                raise ValidationError(f"Skill '{new_code}' already exists.")
            skill.skill = new_code
        if 'description' in data:
            skill.description = data['description'].strip()
        if 'is_active' in data:
            skill.is_active = data['is_active']

        try:
            skill.full_clean()
            skill.save()
            return skill
        except IntegrityError as e:
            logger.error("Database error when updating skill '%s': %s", skill_id, e)
            raise ValidationError(f"Skill '{skill_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating skill '%s': %s", skill_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating skill '%s': %s", skill_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_skill(skill_id: int):
        """
        Deletes the specified skill id.
        """
        if not skill_id:
            raise ValidationError("Invalid: skill_id must be an integer and greater than 0.")

        skill = Skill.objects.get(pk=skill_id)
        if not skill:
            raise ValidationError(f"Skill '{skill_id}' does not exist.")

        try:
            skill.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting skill '%s': %s", skill_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting skill '%s': %s", skill_id, e)
            raise

    @staticmethod
    def list_members(skill_id: int, page=1, page_size=20, include_inactive=False):
        """
        List all members associated with specified skill.
        """
        if not skill_id:
            raise ValidationError("Invalid: skill_id must be an integer and greater than 0.")

        skill = Skill.objects.get(pk=skill_id)
        if not skill:
            raise ValidationError(f"Skill '{skill_id}' does not exist.")

        from apps.team_members.models import TeamMember
        if include_inactive:
            qs = TeamMember.objects.filter(
                skills=skill
            ).order_by('last_name', 'first_name')
        else:
            qs = TeamMember.objects.filter(
                is_active=True, skills=skill
            ).order_by('last_name', 'first_name')

        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    def _validate_row(data: dict) -> None:
        """
        Validate a single import row without writing to the database.
        Raises ValidationError with a user-facing message on any failure.
        Used by both the dry-run path and the real import path.
        """
        skill = data.get('skill', '').strip().upper()
        if not skill:
            raise ValidationError("'skill' is required and cannot be blank.")
        if len(skill) > 20:
            raise ValidationError("'skill' must be 20 characters or fewer.")
        if Skill.objects.filter(skill=skill).exists():
            raise ValidationError(f"Skill '{skill}' already exists.")

    @staticmethod
    def bulk_import(request, dry_run=False):
        file = request.FILES.get("file")
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith(".csv"):
            raise ValidationError("Only CSV files are supported.")

        rows: list[dict] = []
        try:
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError as e:
            logger.warning("Unicode error when reading file.")
            raise ValidationError("File encoding must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"Maximum {MAX_ROWS} rows allowed per import.")

        results = {
            "succeeded": [],
            "failed": [],
            "total": len(rows),
            "dry_run": dry_run,
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):  # start=2 to account for header row
            skill = row.get('skill', '').strip().upper()
            try:
                data = {
                    "skill": skill,
                    "description": row.get('description', '').strip(),
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                }

                if dry_run:
                    # Validate only — no DB writes.
                    SkillService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": skill})
                else:
                    # Full import — _validate_row is also called inside create_team.
                    skill = SkillService.create_skill(data)
                    results["succeeded"].append({"row": index, "name": skill.skill})
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": row.get('skill'),
                    "error": e.messages if hasattr(e, 'messages') else str(e),
                })

        if dry_run:
            results["summary"] = (
                f"Validation complete: {len(results['succeeded'])} rows valid, "
                f"{len(results['failed'])} rows have errors."
            )
        else:
            results["summary"] = (
                f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
            )

        return results
