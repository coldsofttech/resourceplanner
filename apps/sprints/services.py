import logging
from datetime import date

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone

from .models import Sprint

logger = logging.getLogger(__name__)


class SprintService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_sprints(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {'sprint_number', 'sprint_name', 'start_date', 'end_date', 'month', 'is_active'}
        qs = Sprint.objects.select_related('financial_year').all()

        if filters:
            if filters.get('search'):
                term = filters['search']
                qs = qs.filter(sprint_name__icontains=term) | qs.filter(notes__icontains=term)

            if filters.get('fy_id'):
                qs = qs.filter(financial_year_id=filters['fy_id'])

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = SprintService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

            if filters.get('month'):
                qs = qs.filter(month=filters['month'])

            # Date range filters
            if filters.get('start_date_from'):
                qs = qs.filter(start_date__gte=filters['start_date_from'])
            if filters.get('end_date_to'):
                qs = qs.filter(end_date__lte=filters['end_date_to'])

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'sprint_number'
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by('financial_year', order_field)

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
    def list_sprints_for_fy(fy_id: int):
        """Lightweight list for a single FY — used by the FY detail view."""
        if not fy_id:
            raise ValidationError("Invalid: fy_id must be an integer and greater than 0.")

        from apps.financial_years.models import FinancialYear
        fy = FinancialYear.objects.get(id=fy_id)
        if not fy:
            raise ValidationError(f"Financial year '{fy_id} does not exist.")

        return (
            Sprint.objects
            .filter(financial_year_id=fy_id)
            .order_by('sprint_number')
        )

    @staticmethod
    def list_stats(fy_id=None, fields=None):
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = Sprint.objects.all()
        result = {}
        if fy_id:
            from apps.financial_years.models import FinancialYear
            fy = FinancialYear.objects.get(id=fy_id)
            if not fy:
                raise ValidationError(f"Financial year '{fy_id}' does not exist.")
            qs = qs.filter(financial_year_id=fy_id)

        today = timezone.localdate()
        active_sprint = qs.filter(is_active=True).first()

        if wants("total_sprints"):
            result["total_sprints"] = qs.count()
        if wants("active_sprint"):
            result["active_sprint"] = active_sprint.sprint_name if active_sprint else None
        if wants("active_sprint_start_date"):
            result["active_sprint_start_date"] = active_sprint.start_date if active_sprint else None
        if wants("active_sprint_end_date"):
            result["active_sprint_end_date"] = active_sprint.end_date if active_sprint else None
        if wants("active_sprint_remaining_days"):
            result["active_sprint_remaining_days"] = (active_sprint.end_date - today).days if active_sprint else None
        if wants("overridden_sprints"):
            result["overridden_sprints"] = qs.filter(is_overridden=True).count()
        if wants("completed_sprints"):
            result["completed_sprints"] = qs.filter(end_date__lt=today).count()
        if wants("upcoming_sprints"):
            result["upcoming_sprints"] = qs.filter(start_date__gt=today).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        from apps.financial_years.models import FinancialYear
        ds = {
            "is_active": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
            "months": [
                {"value": i, "label": date(2000, i, 1).strftime("%b")}
                for i in range(1, 13)
            ],
            "financial_years": [
                {"value": fy.pk, "label": fy.long_fy, "is_active": fy.is_active}
                for fy in FinancialYear.objects.order_by(
                    "-start_date"
                )
            ]
        }
        result = {}

        if wants("is_active"):
            result["is_active"] = ds["is_active"]
        if wants("months"):
            result["months"] = ds["months"]
        if wants("financial_years"):
            result["financial_years"] = ds["financial_years"]

        return result

    @staticmethod
    def get_sprint(sprint_id: int):
        if not sprint_id:
            raise ValidationError("sprint_id must be a positive integer.")

        return Sprint.objects.select_related('financial_year').get(pk=sprint_id)

    @staticmethod
    def get_active_sprint():
        """Returns the active sprint or None."""
        return (
            Sprint.objects
            .filter(is_active=True)
            .select_related('financial_year')
            .first()
        )

    @staticmethod
    @transaction.atomic
    def create_sprint(data: dict):
        if not isinstance(data, dict):
            raise ValidationError("data must be a dictionary.")
        if 'start_date' not in data or 'end_date' not in data:
            raise ValidationError("Invalid: 'start_date' and 'end_date' are required.")

        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date > end_date:
            raise ValidationError("'start_date' must be on or before 'end_date'.")

        fy = data['financial_year']
        if start_date < fy.start_date or end_date > fy.end_date:
            raise ValidationError(
                f"Sprint dates must fall within the financial year window "
                f"({fy.start_date} – {fy.end_date})."
            )

        # Overlap check
        SprintService._check_overlap(fy.pk, start_date, end_date)
        sprint_number = data.get('sprint_number')
        if not sprint_number:
            raise ValidationError("'sprint_number' is required.")

        if Sprint.objects.filter(financial_year=fy, sprint_number=sprint_number).exists():
            raise ValidationError(
                f"Sprint number {sprint_number} already exists in this financial year."
            )

        try:
            sprint = Sprint(
                financial_year=fy,
                sprint_number=sprint_number,
                sprint_name=(data.get("sprint_name") or "").strip(),
                start_date=start_date,
                end_date=end_date,
                is_active=data.get('is_active', False),
                notes=(data.get('notes') or '').strip(),
            )
            sprint.full_clean()
            sprint.save()

            return sprint
        except IntegrityError as e:
            logger.error("Database error when creating sprint '%s': %s", sprint_number, e)
            raise ValidationError(f"Sprint '{sprint_number}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating sprint '%s': %s", sprint_number, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating sprint '%s': %s", sprint_number, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_sprint(sprint_id: int, data: dict):
        if not sprint_id:
            raise ValidationError("Invalid: sprint_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        sprint = Sprint.objects.select_related('financial_year').get(pk=sprint_id)
        if not sprint:
            raise ValidationError(f"Sprint '{sprint_id}' does not exist.")

        fy = sprint.financial_year

        old_start_date = sprint.start_date
        old_end_date = sprint.end_date
        old_name = sprint.sprint_name

        start_date = data.get('start_date', old_start_date)
        end_date = data.get('end_date', old_end_date)

        if start_date > end_date:
            raise ValidationError("'start_date' must be on or before 'end_date'.")
        if start_date < fy.start_date or end_date > fy.end_date:
            raise ValidationError(
                f"Sprint dates must fall within the financial year window "
                f"({fy.start_date} – {fy.end_date})."
            )

        SprintService._check_overlap(fy.pk, start_date, end_date, exclude_pk=sprint_id)

        is_overridden = False
        if 'start_date' in data:
            sprint.start_date = start_date
            if old_start_date != sprint.start_date:
                is_overridden = True
        if 'end_date' in data:
            sprint.end_date = end_date
            if old_end_date != sprint.end_date:
                is_overridden = True
        if 'sprint_name' in data:
            sprint.sprint_name = data['sprint_name'].strip()
            if old_name != sprint.sprint_name:
                is_overridden = True
        if 'notes' in data:
            sprint.notes = (data.get('notes') or '').strip()

        if is_overridden:
            sprint.is_overridden = True

        try:
            if 'is_active' in data:
                if data['is_active'] and not sprint.is_active:
                    Sprint.objects.filter(is_active=True).exclude(pk=sprint_id).update(is_active=False)
                sprint.is_active = data['is_active']

            sprint.full_clean()
            sprint.save()
            return sprint
        except IntegrityError as e:
            logger.error("Database error when updating sprint '%s': %s", sprint_id, e)
            raise ValidationError(f"Sprint '{sprint_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating sprint '%s': %s", sprint_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating sprint '%s': %s", sprint_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_sprint(sprint_id: int):
        if not sprint_id:
            raise ValidationError("Invalid: sprint_id must be an integer and greater than 0.")

        sprint = Sprint.objects.get(pk=sprint_id)
        if not sprint:
            raise ValidationError(f"Sprint '{sprint_id}' does not exist.")

        try:
            sprint.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting sprint '%s': %s", sprint_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting sprint '%s': %s", sprint_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def set_active(sprint_id: int):
        """
        Marks the specified sprint as active and deactivates all others.
        Returns the newly active sprint.
        """
        if not sprint_id:
            raise ValidationError("Invalid: sprint_id must be an integer and greater than 0.")

        sprint = Sprint.objects.get(pk=sprint_id)
        if not sprint:
            raise ValidationError(f"Sprint '{sprint_id}' does not exist.")

        if sprint.end_date and sprint.end_date < timezone.localdate():
            raise ValidationError("Cannot active a completed sprint.")

        try:
            Sprint.objects.exclude(pk=sprint_id).update(is_active=False)
            sprint.is_active = True
            sprint.save(update_fields=['is_active', 'updated_at'])
            return sprint
        except DatabaseError as e:
            logger.exception("Database error when updating sprint '%s': %s", sprint_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating sprint '%s': %s", sprint_id, e)
            raise

    @staticmethod
    def list_summary(fy_id=None):
        qs = Sprint.objects.select_related('financial_year').order_by('-start_date')

        if fy_id is not None:
            qs = qs.filter(financial_year_id=fy_id)

        return qs

    @staticmethod
    def _check_overlap(fy_id: int, start_date: date, end_date: date, exclude_pk: int = None):
        qs = Sprint.objects.filter(
            financial_year_id=fy_id,
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            conflict = qs.first()
            raise ValidationError(
                f"Dates overlap with existing sprint '{conflict.sprint_name}' "
                f"({conflict.start_date} – {conflict.end_date})."
            )
