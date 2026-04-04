import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .models import DeliveryTeam

logger = logging.getLogger(__name__)


class DeliveryTeamService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_teams(filters=None, page=1, page_size=20):
        """
        List the delivery teams. 
        Supports filters: search, is_active
        """
        VALID_ORDER_FIELDS = {'name', 'member_count', 'is_active'}
        qs = DeliveryTeam.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(name__icontains=s_term) | qs.filter(description__icontains=s_term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = DeliveryTeamService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'name'
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
        List the statistics of the delivery teams.
        Supports filters: fields
        """
        from apps.team_members.models import TeamMember
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = DeliveryTeam.objects.all()
        result = {}

        if wants("total_teams"):
            result["total_teams"] = qs.count()
        if wants("active_teams"):
            result["active_teams"] = qs.filter(is_active=True).count()
        if wants("inactive_teams"):
            result["inactive_teams"] = qs.filter(is_active=False).count()
        if wants("total_members"):
            result["total_members"] = TeamMember.objects.filter(is_active=True).count()
        if wants("unassigned_members"):
            result["unassigned_members"] = TeamMember.objects.filter(is_active=True, team__isnull=True).count()

        return result

    @staticmethod
    def list_options(fields=None):
        """
        List the options available for fields of delivery teams.
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
    def get_team(team_id: int):
        """
        Returns the details of the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team_id must be an integer and greater than 0.")

        return DeliveryTeam.objects.get(pk=team_id)

    @staticmethod
    @transaction.atomic
    def create_team(data: dict):
        """
        Creates new team.
        """
        if not isinstance(data, dict) or 'name' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'name' is a required field.")

        team_name = data['name'].strip()
        if not team_name:
            raise ValidationError("Invalid: name cannot be blank.")

        # Verify whether team already exists
        if DeliveryTeam.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Team '{data['name']}' already exists.")

        # Create the team
        try:
            team = DeliveryTeam(
                name=team_name,
                description=data.get('description', '').strip(),
                is_active=data.get('is_active', True),
            )
            team.full_clean()
            team.save()
            return team
        except IntegrityError as e:
            logger.error("Database error when creating team '%s': %s", team_name, e)
            raise ValidationError(f"Team '{team_name}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating team '%s': %s", team_name, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating team '%s': %s", team_name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_team(team_id: int, data: dict):
        """
        Updates the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        team = DeliveryTeam.objects.get(pk=team_id)
        if not team:
            raise ValidationError(f"Team '{team_id}' does not exist.")

        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if DeliveryTeam.objects.filter(name=new_name).exclude(pk=team_id).exists():
                raise ValidationError(f"Team '{new_name}' already exists.")
            team.name = new_name
        if 'description' in data:
            team.description = data['description'].strip()
        if 'is_active' in data:
            team.is_active = data['is_active']

        try:
            team.full_clean()
            team.save()
            return team
        except IntegrityError as e:
            logger.error("Database error when updating team '%s': %s", team_id, e)
            raise ValidationError(f"Team '{team_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating team '%s': %s", team_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating team '%s': %s", team_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_team(team_id: int):
        """
        Deletes the specified team id.
        """
        if not team_id:
            raise ValidationError("Invalid: team id must be an integer and greater than 0.")

        team = DeliveryTeam.objects.get(pk=team_id)
        if not team:
            raise ValidationError(f"Team '{team_id}' does not exist.")

        try:
            team.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting team '%s': %s", team_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting team '%s': %s", team_id, e)
            raise

    @staticmethod
    def list_members(team_id: int, page=1, page_size=20, include_inactive=False):
        """
        List all members associated with specified team.
        """
        if not team_id:
            raise ValidationError("Invalid: team_id must be an integer and greater than 0.")

        team = DeliveryTeam.objects.get(pk=team_id)
        if not team:
            raise ValidationError(f"Team '{team_id}' does not exist.")

        from apps.team_members.models import TeamMember
        if include_inactive:
            qs = TeamMember.objects.filter(
                team=team
            ).order_by('last_name', 'first_name')
        else:
            qs = TeamMember.objects.filter(
                is_active=True, team=team
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
    def list_leaves(team_id: int, page=1, page_size=20, include_past=False):
        """
        List all leaves associated with specified team.
        """
        if not team_id:
            raise ValidationError("Invalid: team_id must be an integer and greater than 0.")

        # Raises DoesNotExist if not found — let the view catch it
        team = DeliveryTeam.objects.get(pk=team_id)

        from apps.member_leaves.models import MemberLeave
        qs = (
            MemberLeave.objects
            .filter(member__team=team, member__is_active=True)
            .select_related('member', 'member__location')
            .order_by('start_date', 'member__last_name', 'member__first_name')
        )

        if not include_past:
            qs = qs.filter(end_date__gte=timezone.localdate())

        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            'results': page_obj.object_list,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'page_size': page_size,
        }

    @staticmethod
    def _validate_row(data: dict) -> None:
        """
        Validate a single import row without writing to the database.
        Raises ValidationError with a user-facing message on any failure.
        Used by both the dry-run path and the real import path.
        """
        name = data.get('name', '').strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")
        if len(name) > 120:
            raise ValidationError("'name' must be 120 characters or fewer.")
        if DeliveryTeam.objects.filter(name=name).exists():
            raise ValidationError(f"Team '{name}' already exists.")

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
            name = row.get('name', '').strip()
            try:
                data = {
                    "name": name,
                    "description": row.get('description', '').strip(),
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                }

                if dry_run:
                    # Validate only — no DB writes.
                    DeliveryTeamService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": name})
                else:
                    # Full import — _validate_row is also called inside create_team.
                    team = DeliveryTeamService.create_team(data)
                    results["succeeded"].append({"row": index, "name": team.name})
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": row.get('name'),
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
