import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import EmploymentType

logger = logging.getLogger(__name__)


class EmploymentTypeService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_employment_types(filters=None, page=1, page_size=20):
        """
        List the employment types.
        Supports filters: search, is_active
        """
        VALID_ORDER_FIELDS = {'name', 'is_active'}
        qs = EmploymentType.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(name__icontains=s_term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = EmploymentTypeService._parse_bool(is_active_raw)
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
        List the statistics of the employment types.
        Supports filters: fields
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = EmploymentType.objects.all()
        result = {}

        if wants("total_types"):
            result["total_types"] = qs.count()
        if wants("active_types"):
            result["active_types"] = qs.filter(is_active=True).count()
        if wants("inactive_types"):
            result["inactive_types"] = qs.filter(is_active=False).count()

        return result

    @staticmethod
    def list_options(fields=None):
        """
        List the options available for fields of employment types.
        Supports filters: fields
        """

        def wants(field):
            return fields is None or field in fields

        ds = {
            "is_active": [
                {"value": True,  "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
            "is_default": [
                {"value": True,  "label": "Default"},
                {"value": False, "label": "Not default"},
            ],
        }
        result = {}

        if wants("is_active"):
            result["is_active"] = ds["is_active"]
        if wants("is_default"):
            result["is_default"] = ds["is_default"]

        return result

    @staticmethod
    def get_employment_type(type_id: int):
        """
        Returns the details of the specified employment type id.
        """
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")

        return EmploymentType.objects.get(pk=type_id)

    @staticmethod
    @transaction.atomic
    def create_employment_type(data: dict):
        """
        Creates a new employment type.
        """
        if not isinstance(data, dict) or 'name' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'name' is a required field.")

        name = data['name'].strip()
        if not name:
            raise ValidationError("Invalid: name cannot be blank.")

        if EmploymentType.objects.filter(name=name).exists():
            raise ValidationError(f"Employment type '{name}' already exists.")

        try:
            if data.get('is_default', False):
                EmploymentType.objects.filter(is_default=True).update(is_default=False)

            employment_type = EmploymentType(
                name=name,
                is_active=data.get('is_active', True),
                is_default=data.get('is_default', False),
            )
            employment_type.full_clean()
            employment_type.save()
            return employment_type
        except IntegrityError as e:
            logger.error("Database error when creating employment type '%s': %s", name, e)
            raise ValidationError(f"Employment type '{name}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating employment type '%s': %s", name, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating employment type '%s': %s", name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_employment_type(type_id: int, data: dict):
        """
        Updates the specified employment type id.
        """
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        employment_type = EmploymentType.objects.get(pk=type_id)
        if not employment_type:
            raise ValidationError(f"Employment type '{type_id}' does not exist.")

        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if EmploymentType.objects.filter(name=new_name).exclude(pk=type_id).exists():
                raise ValidationError(f"Employment type '{new_name}' already exists.")
            employment_type.name = new_name
        if 'is_active' in data:
            employment_type.is_active = data['is_active']
        if 'is_default' in data:
            if data['is_default']:
                EmploymentType.objects.exclude(pk=type_id).filter(is_default=True).update(is_default=False)
            employment_type.is_default = data['is_default']

        try:
            employment_type.full_clean()
            employment_type.save()
            return employment_type
        except IntegrityError as e:
            logger.error("Database error when updating employment type '%s': %s", type_id, e)
            raise ValidationError(f"Employment type '{type_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating employment type '%s': %s", type_id, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating employment type '%s': %s", type_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_employment_type(type_id: int):
        """
        Deletes the specified employment type id.
        """
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")

        employment_type = EmploymentType.objects.get(pk=type_id)
        if not employment_type:
            raise ValidationError(f"Employment type '{type_id}' does not exist.")

        try:
            employment_type.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting employment type '%s': %s", type_id, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting employment type '%s': %s", type_id, e)
            raise

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
        if len(name) > 100:
            raise ValidationError("'name' must be 100 characters or fewer.")
        if EmploymentType.objects.filter(name=name).exists():
            raise ValidationError(f"Employment type '{name}' already exists.")

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
        except UnicodeDecodeError:
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
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                }

                if dry_run:
                    EmploymentTypeService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": name})
                else:
                    employment_type = EmploymentTypeService.create_employment_type(data)
                    results["succeeded"].append({"row": index, "name": employment_type.name})
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
