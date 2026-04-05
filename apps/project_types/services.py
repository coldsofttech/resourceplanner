import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import ProjectType

logger = logging.getLogger(__name__)


class ProjectTypeService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_types(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {'name'}
        qs = ProjectType.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(name__icontains=s_term) | qs.filter(description__icontains=s_term)

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
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = ProjectType.objects.all()
        result = {}

        if wants("total_types"):
            result["total_types"] = qs.count()
        if wants("assigned_types"):
            result["assigned_types"] = 0  # TODO: implement once projects module is in place
        if wants("unassigned_types"):
            result["unassigned_types"] = 0  # TODO: implement once projects module is in place

        return result

    @staticmethod
    def get_type(type_id: int):
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")

        return ProjectType.objects.get(pk=type_id)

    @staticmethod
    @transaction.atomic
    def create_type(data: dict):
        if not isinstance(data, dict) or 'name' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'name' is a required field.")

        type_name = data['name'].strip()
        if not type_name:
            raise ValidationError("Invalid: name cannot be blank.")

        # Verify whether type already exists
        if ProjectType.objects.filter(name=data['name']).exists():
            raise ValidationError(f"Project type '{data['name']}' already exists.")

        # Create the type
        try:
            _type = ProjectType(
                name=type_name,
                description=data.get('description', '').strip(),
            )
            _type.full_clean()
            _type.save()
            return _type
        except IntegrityError as e:
            logger.error("Database error when creating type '%s': %s", type_name, e)
            raise ValidationError(f"Project type '{type_name}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating type '%s': %s", type_name, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating type '%s': %s", type_name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_type(type_id: int, data: dict):
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        _type = ProjectType.objects.get(pk=type_id)
        if not _type:
            raise ValidationError(f"Project type '{type_id}' does not exist.")

        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if ProjectType.objects.filter(name=new_name).exclude(pk=type_id).exists():
                raise ValidationError(f"Project type '{new_name}' already exists.")
            _type.name = new_name
        if 'description' in data:
            _type.description = data['description'].strip()

        try:
            _type.full_clean()
            _type.save()
            return _type
        except IntegrityError as e:
            logger.error("Database error when updating type '%s': %s", type_id, e)
            raise ValidationError(f"Project type '{type_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating type '%s': %s", type_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating type '%s': %s", type_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_type(type_id: int):
        if not type_id:
            raise ValidationError("Invalid: type_id must be an integer and greater than 0.")

        _type = ProjectType.objects.get(pk=type_id)
        if not _type:
            raise ValidationError(f"Project type '{type_id}' does not exist.")

        try:
            _type.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting type '%s': %s", type_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting type '%s': %s", type_id, e)
            raise

    @staticmethod
    def _validate_row(data: dict):
        """
        Validate a single import row without writing to the database.
        Raises ValidationError with a user-facing message on any failure.
        Used by both the dry-run path and the real import path.
        """
        name = data.get('name', '').strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")
        if len(name) > 60:
            raise ValidationError("'name' must be 60 characters or fewer.")
        if ProjectType.objects.filter(name=name).exists():
            raise ValidationError(f"Project type '{name}' already exists.")

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
                }

                if dry_run:
                    # Validate only — no DB writes.
                    ProjectTypeService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": name})
                else:
                    # Full import — _validate_row is also called inside create_type.
                    _type = ProjectTypeService.create_type(data)
                    results["succeeded"].append({"row": index, "name": _type.name})
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
