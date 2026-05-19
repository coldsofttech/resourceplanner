import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import TeamRole

logger = logging.getLogger(__name__)


class TeamRoleService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_roles(filters=None, page=1, page_size=20):
        """
        List the team roles.
        Supports filters: search, is_active
        """
        VALID_ORDER_FIELDS = {'role', 'is_active', 'is_assignable'}
        qs = TeamRole.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(role__icontains=s_term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = TeamRoleService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

            if filters.get('is_assignable') is not None:
                is_assignable_raw = filters['is_assignable']
                is_assignable = TeamRoleService._parse_bool(is_assignable_raw)
                qs = qs.filter(is_assignable=is_assignable)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'role'
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
        List the statistics of the team roles.
        Supports filters: fields
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = TeamRole.objects.all()
        result = {}

        if wants("total_roles"):
            result["total_roles"] = qs.count()
        if wants("active_roles"):
            result["active_roles"] = qs.filter(is_active=True).count()
        if wants("inactive_roles"):
            result["inactive_roles"] = qs.filter(is_active=False).count()
        if wants("unassigned_roles"):
            result["unassigned_roles"] = 0  # TODO: Total no of roles unassigned to team members
        if wants("assignable_roles"):
            result["assignable_roles"] = qs.filter(is_assignable=True).count()

        return result

    @staticmethod
    def list_options(fields=None):
        """
        List the options available for fields of team roles.
        Supports filters: fields
        """

        def wants(field):
            return fields is None or field in fields

        ds = {
            "is_active": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
            "is_assignable": [
                {"value": True, "label": "Assignable"},
                {"value": False, "label": "Not assignable"},
            ],
            "is_default": [
                {"value": True, "label": "Default"},
                {"value": False, "label": "Not default"},
            ],
        }
        result = {}

        if wants("is_active"):
            result["is_active"] = ds["is_active"]
        if wants("is_assignable"):
            result["is_assignable"] = ds["is_assignable"]
        if wants("is_default"):
            result["is_default"] = ds["is_default"]

        return result

    @staticmethod
    def get_role(role_id: int):
        """
        Returns the details of the specified role id.
        """
        if not role_id:
            raise ValidationError("Invalid: role_id must be an integer and greater than 0.")

        role = TeamRole.objects.get(pk=role_id)

        from apps.team_members.models import TeamMember
        members = TeamMember.objects.filter(role=role)
        role.total_members = members.count()
        role.active_members = members.filter(is_active=True).count()
        role.inactive_members = members.filter(is_active=False).count()

        return role

    @staticmethod
    @transaction.atomic
    def create_role(data: dict):
        """
        Creates a new team role.
        """
        if not isinstance(data, dict) or 'role' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'role' is a required field.")

        role_name = data['role'].strip()
        if not role_name:
            raise ValidationError("Invalid: role cannot be blank.")

        # Verify whether role already exists
        if TeamRole.objects.filter(role=role_name).exists():
            raise ValidationError(f"Role '{role_name}' already exists.")

        # Create the role
        try:
            if data.get('is_default', False):
                TeamRole.objects.filter(is_default=True).update(is_default=False)

            role = TeamRole(
                role=role_name,
                is_active=data.get('is_active', True),
                is_default=data.get('is_default', False),
                is_assignable=data.get('is_assignable', False),
                is_shareable=data.get('is_shareable', False),
            )
            role.full_clean()
            role.save()
            return role
        except IntegrityError as e:
            logger.error("Database error when creating role '%s': %s", role_name, e)
            raise ValidationError(f"Role '{role_name}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating role '%s': %s", role_name, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating role '%s': %s", role_name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_role(role_id: int, data: dict):
        """
        Updates the specified role id.
        """
        if not role_id:
            raise ValidationError("Invalid: role_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        role = TeamRole.objects.get(pk=role_id)
        if not role:
            raise ValidationError(f"Role '{role_id}' does not exist.")

        if 'role' in data:
            new_name = data['role'].strip()
            if not new_name:
                raise ValidationError("Invalid: role cannot be blank.")
            if TeamRole.objects.filter(role=new_name).exclude(pk=role_id).exists():
                raise ValidationError(f"Role '{new_name}' already exists.")
            role.role = new_name
        if 'is_active' in data:
            role.is_active = data['is_active']
        if 'is_default' in data:
            if data['is_default']:
                TeamRole.objects.exclude(pk=role_id).filter(is_default=True).update(is_default=False)
            role.is_default = data['is_default']
        if 'is_assignable' in data:
            role.is_assignable = data['is_assignable']
        if 'is_shareable' in data:
            role.is_shareable = data['is_shareable']

        try:
            role.full_clean()
            role.save()
            return role
        except IntegrityError as e:
            logger.error("Database error when updating role '%s': %s", role_id, e)
            raise ValidationError(f"Role '{role_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating role '%s': %s", role_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating role '%s': %s", role_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_role(role_id: int):
        """
        Deletes the specified role id.
        """
        if not role_id:
            raise ValidationError("Invalid: role_id must be an integer and greater than 0.")

        role = TeamRole.objects.get(pk=role_id)
        if not role:
            raise ValidationError(f"Role '{role_id}' does not exist.")

        try:
            role.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting role '%s': %s", role_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting role '%s': %s", role_id, e)
            raise

    @staticmethod
    def list_members(role_id: int, page=1, page_size=20, include_inactive=False):
        """
        List all members associated with specified role.
        """
        if not role_id:
            raise ValidationError("Invalid: role_id must be an integer and greater than 0.")

        role = TeamRole.objects.get(pk=role_id)
        if not role:
            raise ValidationError(f"Role '{role_id}' does not exist.")

        from apps.team_members.models import TeamMember
        if include_inactive:
            qs = TeamMember.objects.filter(
                role=role
            ).order_by('last_name', 'first_name')
        else:
            qs = TeamMember.objects.filter(
                is_active=True, role=role
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
        role = data.get('role', '').strip()
        if not role:
            raise ValidationError("'role' is required and cannot be blank.")
        if len(role) > 100:
            raise ValidationError("'role' must be 100 characters or fewer.")
        if TeamRole.objects.filter(role=role).exists():
            raise ValidationError(f"Role '{role}' already exists.")

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
            role_name = row.get('role', '').strip()
            try:
                data = {
                    "role": role_name,
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                    "is_assignable": (row.get('is_assignable') or 'false').strip().lower() == "true",
                }

                if dry_run:
                    # Validate only — no DB writes.
                    TeamRoleService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": role_name})
                else:
                    # Full import — _validate_row is also called inside create_role.
                    role = TeamRoleService.create_role(data)
                    results["succeeded"].append({"row": index, "name": role.role})
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": row.get('role'),
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
