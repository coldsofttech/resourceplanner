import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction

from .models import Skill

logger = logging.getLogger(__name__)


class SkillService:
    @staticmethod
    def list_skills(filters=None):
        """
        List the skills.
        Supports filters: search, is_active
        """
        qs = Skill.objects.all()

        if not filters:
            return qs

        if filters.get('search'):
            s_term = filters['search']
            qs = qs.filter(skill__icontains=s_term) | qs.filter(description__icontains=s_term)

        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])

        return qs

    @staticmethod
    def get_skill(skill_id: int):
        """
        Returns the details of the specified skill id.
        """
        if not skill_id:
            raise ValidationError("Invalid: skill_id must be an integer and greater than 0.")

        return Skill.objects.get(pk=skill_id)

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
    def bulk_import(request):
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
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):  # start=2 to account for header row
            try:
                skill = SkillService.create_skill({
                    "skill": row.get('skill', '').strip(),
                    "description": row.get('description', '').strip(),
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                })
                results["succeeded"].append({
                    "row": index,
                    "skill": skill.skill
                })
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "skill": row.get('skill'),
                    "error": e.messages if hasattr(e, 'messages') else str(e),
                })

        results["summary"] = f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
        return results
