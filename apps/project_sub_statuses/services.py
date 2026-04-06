import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import F

from .models import ProjectSubStatus

logger = logging.getLogger(__name__)

PROJECT_SUB_STATUS_DEFAULTS = {
    "NOT_STARTED": {
        "name": "Not Started",
        "main_status": "NEW",
        "order": 1,
        "is_active": True,
    },
    "UNDER_REVIEW": {
        "name": "Under Review",
        "main_status": "NEW",
        "order": 2,
        "is_active": True,
    },
    "ESTIMATES_SHARED": {
        "name": "Estimates Shared",
        "main_status": "NEW",
        "order": 3,
        "is_active": True,
    },
    "ESTIMATES_APPROVED": {
        "name": "Estimates Approved",
        "main_status": "NEW",
        "order": 4,
        "is_active": True,
    },
    "START_DATE_CONFIRMED": {
        "name": "Start Date Confirmed",
        "main_status": "NEW",
        "order": 5,
        "is_active": True,
    },
    "IN_PROGRESS": {
        "name": "In Progress",
        "main_status": "IN_PROGRESS",
        "order": 1,
        "is_active": True,
    },
    "BLOCKED": {
        "name": "Blocked",
        "main_status": "IN_PROGRESS",
        "order": 2,
        "is_active": True,
    },
    "ON_HOLD": {
        "name": "On Hold",
        "main_status": "ON_HOLD",
        "order": 1,
        "is_active": True,
    },
    "AWAITING_BUDGET": {
        "name": "Awaiting Budget",
        "main_status": "ON_HOLD",
        "order": 2,
        "is_active": True,
    },
    "AWAITING_RESOURCE": {
        "name": "Awaiting Resource",
        "main_status": "ON_HOLD",
        "order": 3,
        "is_active": True,
    },
    "COMPLETED": {
        "name": "Completed",
        "main_status": "COMPLETED",
        "order": 1,
        "is_active": True,
    },
    "SIGNED_OFF": {
        "name": "Signed Off",
        "main_status": "COMPLETED",
        "order": 2,
        "is_active": True,
    },
    "STOPPED": {
        "name": "Stopped",
        "main_status": "CANCELLED",
        "order": 1,
        "is_active": True,
    },
    "CANCELLED": {
        "name": "Cancelled",
        "main_status": "CANCELLED",
        "order": 2,
        "is_active": True,
    },
}


class ProjectSubStatusService:
    MAIN_STATUSES = ['NEW', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED']
    ORDERING_MAP = {
        "default": ["main_status", "order", "name"],
        "name": ["name"],
        "main_status": ["main_status", "order"],
        "active": ["-is_active", "main_status", "order"],
    }

    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_statuses(filters=None, main_status=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {'name', 'main_status', 'is_active'}
        qs = ProjectSubStatus.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(name__icontains=s_term)
            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = ProjectSubStatusService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)
            if filters.get('main_status') is not None:
                qs = qs.filter(main_status__icontains=filters['main_status'])

        order_by = filters.get('order_by') if filters else "default"
        order_dir = filters.get('order_dir') if filters else None
        order_fields = ProjectSubStatusService.ORDERING_MAP[order_by or "default"]
        if order_dir == 'desc':
            order_fields = [f"-{field}" for field in order_fields]
        qs = qs.order_by(*order_fields)

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
    def list_options(fields=None, main_status=None):
        def wants(field):
            return fields is None or field in fields

        result = {}

        if wants("is_active"):
            result["is_active"] = [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]

        if wants("main_status"):
            statuses_to_include = (
                [main_status]
                if main_status and main_status in ProjectSubStatusService.MAIN_STATUSES
                else ProjectSubStatusService.MAIN_STATUSES
            )
            result["main_status"] = {
                ms: [
                    {"value": ss.pk, "label": ss.name, "order": ss.order}
                    for ss in ProjectSubStatus.objects.filter(
                        main_status=ms, is_active=True
                    ).order_by("order", "name")
                ]
                for ms in statuses_to_include
            }

        return result

    @staticmethod
    def get_status(status_id: int):
        if not status_id:
            raise ValidationError("Invalid: status_id must be an integer and greater than 0.")

        return ProjectSubStatus.objects.get(pk=status_id)

    @staticmethod
    @transaction.atomic
    def create_status(data: dict):
        if not isinstance(data, dict) or 'name' not in data or 'main_status' not in data:
            raise ValidationError("Invalid: data must be a dictionary with 'name' and 'main_status'.")

        name = data["name"].strip()
        if not name:
            raise ValidationError("Invalid: name cannot be blank.")

        main_status = data["main_status"].strip()
        if not main_status:
            raise ValidationError("Invalid: main_status cannot be blank.")
        if main_status.upper() not in ProjectSubStatusService.MAIN_STATUSES:
            raise ValidationError(
                f"Invalid main_status. Expected are: {', '.join(ProjectSubStatusService.MAIN_STATUSES)}")

        if ProjectSubStatus.objects.filter(name=name, main_status=main_status).exists():
            raise ValidationError(f"Project sub status '{name} ({main_status})' already exists.")

        order = data.get('order', None)
        if order is None or order == 0:
            existing = ProjectSubStatus.objects.filter(
                main_status=main_status
            ).order_by('-order').values_list('order', flat=True).first()
            order = (existing or 0) + 1

        try:
            project_status = ProjectSubStatus(
                name=name,
                main_status=main_status,
                order=order,
                is_active=data.get('is_active', True),
            )
            project_status.full_clean()
            project_status.save()
            return project_status
        except IntegrityError as e:
            logger.error("Database error when creating project sub status '%s (%s)': %s", name, main_status, e)
            raise ValidationError(
                f"Project sub status '{name} ({main_status})' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating project sub status '%s (%s)': %s", name, main_status, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating project sub status '%s (%s)': %s", name, main_status, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_status(status_id: int, data: dict):
        if not status_id:
            raise ValidationError("Invalid: status_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        project_status = ProjectSubStatus.objects.get(pk=status_id)
        if not project_status:
            raise ValidationError(f"Project sub status '{status_id}' does not exist.")

        if 'name' in data:
            new_name = data['name'].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if ProjectSubStatus.objects.filter(name=new_name, main_status=project_status.main_status).exclude(
                    pk=status_id).exists():
                raise ValidationError(f"Project sub status '{new_name}' already exists.")
            project_status.name = new_name
        if 'order' in data:
            new_order = int(data['order'])
            old_order = project_status.order

            if new_order != old_order:
                siblings = ProjectSubStatus.objects.filter(
                    main_status=project_status.main_status
                )

                if new_order < old_order:
                    # Moving UP → shift others DOWN
                    siblings.filter(
                        order__gte=new_order,
                        order__lt=old_order
                    ).update(order=F('order') + 1)

                else:
                    # Moving DOWN → shift others UP
                    siblings.filter(
                        order__gt=old_order,
                        order__lte=new_order
                    ).update(order=F('order') - 1)

                project_status.order = new_order
        if 'is_active' in data:
            project_status.is_active = data['is_active']

        try:
            project_status.full_clean()
            project_status.save()
            return project_status
        except IntegrityError as e:
            logger.error("Database error when updating project sub status '%s': %s", status_id, e)
            raise ValidationError(f"Project sub status '{status_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating project sub status '%s': %s", status_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating project sub status '%s': %s", status_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_status(status_id: int):
        if not status_id:
            raise ValidationError("Invalid: status_id must be an integer and greater than 0.")

        project_status = ProjectSubStatus.objects.get(pk=status_id)
        if not project_status:
            raise ValidationError(f"Project sub status '{status_id}' does not exist.")

        try:
            project_status.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting project sub status '%s': %s", status_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting project sub status '%s': %s", status_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def reorder(status_id: int, direction: str):
        if not status_id:
            raise ValidationError("Invalid: status_id must be an integer and greater than 0.")
        if not direction in ("up", "down"):
            raise ValidationError("Invalid: direction must be 'up' or 'down'.")

        project_status = ProjectSubStatus.objects.get(pk=status_id)
        if not project_status:
            raise ValidationError(f"Project sub status '{status_id}' does not exist.")

        siblings = list(
            ProjectSubStatus.objects.filter(
                main_status=project_status.main_status
            ).order_by("order", "name")
        )

        idx = next((i for i, s in enumerate(siblings) if s.pk == int(status_id)), None)
        if idx is None:
            return project_status

        swap_idx = idx - 1 if direction == "up" else idx + 1
        if swap_idx < 0 or swap_idx >= len(siblings):
            return project_status

        neighbour = siblings[swap_idx]

        # Snapshot original orders before the swap
        original_status_order = project_status.order
        original_neighbour_order = neighbour.order

        project_status.order = original_neighbour_order
        neighbour.order = original_status_order

        if project_status.order == neighbour.order:
            project_status.order = neighbour.order - 1 if direction == "up" else neighbour.order + 1

        try:
            project_status.save(update_fields=["order", "updated_at"])
            neighbour.save(update_fields=["order", "updated_at"])
            return project_status
        except IntegrityError as e:
            logger.error("Database error when updating order '%s': %s", status_id, e)
            raise ValidationError(f"Project sub status '{status_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating order '%s': %s", status_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating order '%s': %s", status_id, e)
            raise

    @staticmethod
    def _validate_row(data: dict) -> None:
        name = data.get('name', '').strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")
        if len(name) > 100:
            raise ValidationError("'name' must be 100 characters or fewer.")
        main_status = data.get('main_status', '').strip()
        if not main_status:
            raise ValidationError("'main_status' is required and cannot be blank.")
        if len(main_status) > 20:
            raise ValidationError("'main_status' must be 20 characters or fewer.")
        if main_status not in ProjectSubStatusService.MAIN_STATUSES:
            raise ValidationError(f"'main_status' must be one of '{', '.join(ProjectSubStatusService.MAIN_STATUSES)}'.")
        if ProjectSubStatus.objects.filter(
                name=name, main_status=main_status
        ).exists():
            raise ValidationError(f"Project sub status '{name} ({main_status})' already exists.")
        order = data.get('order', 0)
        if not isinstance(order, int) or order < 0:
            raise ValidationError("'order' must be a non-negative integer.")

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
            main_status = row.get('main_status', '').strip()
            raw_order = row.get('order', '').strip()
            order = int(raw_order) if raw_order and raw_order.isdigit() else 0
            label = f"{name} ({main_status})"

            try:
                data = {
                    "name": name,
                    "main_status": main_status,
                    "order": order,
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                }

                if dry_run:
                    # Validate only — no DB writes.
                    ProjectSubStatusService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": label})
                else:
                    # Full import — _validate_row is also called inside create
                    ProjectSubStatusService.create_status(data)
                    results["succeeded"].append({"row": index, "name": label})
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": label,
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
