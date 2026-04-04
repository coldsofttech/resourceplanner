import csv
import datetime
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .models import FinancialYear

logger = logging.getLogger(__name__)


class FinancialYearService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_financial_years(filters=None, page=1, page_size=20):
        """
        Paginated list with optional search and ordering.
        Supports filters: search, is_active, order_by, order_dir
        """
        VALID_ORDER_FIELDS = {'start_date', 'end_date', 'long_fy', 'is_active', 'span_days'}
        qs = FinancialYear.objects.all()

        if filters:
            if filters.get('search'):
                term = filters['search']
                qs = qs.filter(long_fy__icontains=term) | qs.filter(
                    short_fy__icontains=term
                ) | qs.filter(notes__icontains=term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = FinancialYearService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'start_date'
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
            'results': page_obj.object_list,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'page_size': page_size,
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

        qs = FinancialYear.objects.all()
        result = {}
        today = timezone.localdate()

        if wants('total_fys'):
            result['total_fys'] = qs.count()
        if wants('active_fy'):
            active = qs.filter(is_active=True).first()
            result['active_fy'] = active.long_fy if active else None
        if wants('past_fys'):
            result['past_fys'] = qs.filter(end_date__lt=today).count()
        if wants('future_fys'):
            result['future_fys'] = qs.filter(start_date__gt=today).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        ds = {
            "is_active": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
        }

        result = {}
        if wants('is_active'):
            result['is_active'] = ds['is_active']

        return result

    @staticmethod
    def get_financial_year(fy_id: int):
        if not fy_id:
            raise ValidationError('Invalid: fy_id must be a positive integer.')

        return FinancialYear.objects.get(pk=fy_id)

    @staticmethod
    def get_active_financial_year():
        """Returns the currently active FY or None."""
        return FinancialYear.objects.filter(is_active=True).first()

    @staticmethod
    @transaction.atomic
    def create_financial_year(data: dict):
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")
        if 'start_date' not in data or 'end_date' not in data:
            raise ValidationError("Invalid: 'start_date' and 'end_date' are required.")

        try:
            fy = FinancialYear(
                start_date=data['start_date'],
                end_date=data['end_date'],
                is_active=data.get('is_active', False),
                notes=(data.get('notes') or '').strip(),
            )
            fy.full_clean()

            if fy.is_active:
                # Clear any existing active FY before saving the new one.
                FinancialYear.objects.filter(is_active=True).update(is_active=False)

            fy.save()
            return fy
        except IntegrityError as e:
            logger.error("Database error when creating financial year '%s, %s': %s", data.get('start_date'),
                         data.get('end_date'), e)
            raise ValidationError(
                f"Financial year '{data.get('start_date')}, {data.get('end_date')}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating financial year '%s, %': %s", data.get('start_date'),
                             data.get('end_date'), e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating financial year '%s, %s': %s", data.get('start_date'),
                             data.get('end_date'), e)
            raise

    @staticmethod
    @transaction.atomic
    def update_financial_year(fy_id: int, data: dict):
        if not fy_id:
            raise ValidationError("Invalid: fy_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        fy = FinancialYear.objects.get(pk=fy_id)
        if not fy:
            raise ValidationError(f"Financial year '{fy_id}' could not be found.")

        if 'start_date' in data:
            fy.start_date = data['start_date']
        if 'end_date' in data:
            fy.end_date = data['end_date']
        if 'notes' in data:
            fy.notes = (data['notes'] or '').strip()

        try:
            if 'is_active' in data:
                if data['is_active'] and not fy.is_active:
                    FinancialYear.objects.filter(is_active=True).exclude(pk=fy_id).update(is_active=False)
                fy.is_active = data['is_active']

            fy.full_clean()
            fy.save()
            return fy
        except IntegrityError as e:
            logger.error("Database error when updating financial year '%s': %s", fy_id, e)
            raise ValidationError(f"Financial year '{fy_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating financial year '%s': %s", fy_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating financial year '%s': %s", fy_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_financial_year(fy_id: int):
        if not fy_id:
            raise ValidationError("Invalid: fy_id must be an integer and greater than 0.")

        fy = FinancialYear.objects.get(pk=fy_id)
        if not fy:
            raise ValidationError(f"Financial year '{fy_id}' could not be found.")

        try:
            fy.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting financial year '%s': %s", fy_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting financial year '%s': %s", fy_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def set_active(fy_id: int):
        """
        Sets the given FY as the active one.
        Clears is_active on all other FYs atomically.
        """
        if not fy_id:
            raise ValidationError("Invalid: fy_id must be an integer and greater than 0.")

        fy = FinancialYear.objects.get(pk=fy_id)
        if not fy:
            raise ValidationError(f"Financial year '{fy_id}' could not be found.")

        if fy.end_date and fy.end_date < timezone.localdate():
            raise ValidationError("Cannot activate a completed financial year.")

        try:
            # Clear all first, then activate — single atomic block.
            FinancialYear.objects.exclude(pk=fy_id).update(is_active=False)
            fy.is_active = True
            fy.save(update_fields=['is_active', 'updated_at'])
            return fy
        except DatabaseError as e:
            logger.exception("Database error when updating financial year '%s': %s", fy_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating financial year '%s': %s", fy_id, e)
            raise

    @staticmethod
    def list_summary():
        """All FYs ordered newest-first, suitable for navbar dropdown."""
        return FinancialYear.objects.all().order_by('-start_date')

    @staticmethod
    def _validate_row(data: dict):
        """
        Validate a single import row without writing to the database.
        Raises ValidationError with a user-facing message on any failure.
        Used by both the dry-run path and the real import path.
        """
        start_raw = data.get('start_date', '').strip()
        end_raw = data.get('end_date', '').strip()

        if not start_raw:
            raise ValidationError("'start_date' is required.")
        if not end_raw:
            raise ValidationError("'end_date' is required.")

        try:
            start = datetime.date.fromisoformat(start_raw)
        except ValueError:
            raise ValidationError(f"'start_date' must be YYYY-MM-DD, got '{start_raw}'.")
        try:
            end = datetime.date.fromisoformat(end_raw)
        except ValueError:
            raise ValidationError(f"'end_date' must be YYYY-MM-DD, got '{end_raw}'.")

        if end <= start:
            raise ValidationError("'end_date' must be after 'start_date'.")

        return {
            "start_date": start,
            "end_date": end,
            "note": data.get('note', ''),
        }

    @staticmethod
    def bulk_import(request, dry_run=False):
        file = request.FILES.get('file')
        if not file:
            raise ValidationError('No file provided.')
        if not file.name.endswith('.csv'):
            raise ValidationError('Only CSV files are supported.')

        rows: list[dict] = []
        try:
            decoded = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError:
            logger.warning('Unicode error when reading FY import file.')
            raise ValidationError('File must be UTF-8 encoded.')
        except Exception as e:
            logger.exception('Unexpected error reading FY import file: %s', e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f'Maximum {MAX_ROWS} rows allowed per import.')

        results = {
            'succeeded': [],
            'failed': [],
            'total': len(rows),
            'dry_run': dry_run,
            'summary': '',
        }

        for index, row in enumerate(rows, start=2):  # start=2 accounts for header row
            start_raw = row.get('start_date', '').strip()
            end_raw = row.get('end_date', '').strip()
            label = f'{start_raw} → {end_raw}' if start_raw or end_raw else f'Row {index}'

            try:
                data = {
                    'start_date': start_raw,
                    'end_date': end_raw,
                    'notes': row.get('notes', '').strip(),
                }

                cleaned = FinancialYearService._validate_row(data)
                if dry_run:
                    results['succeeded'].append({'row': index, 'name': f'{start_raw} → {end_raw}'})
                else:
                    # Convert raw strings to date objects for the service
                    fy = FinancialYearService.create_financial_year(cleaned)
                    results['succeeded'].append({'row': index, 'name': fy.long_fy})
            except ValidationError as e:
                results['failed'].append({
                    'row': index,
                    'name': label,
                    'error': e.messages if hasattr(e, 'messages') else str(e),
                })
            except (IntegrityError, DatabaseError) as e:
                logger.exception("DB error on row %s: %s", index, e)
                results["failed"].append({
                    "row": index,
                    "name": label,
                    "error": ["A database error occurred for this row."],
                })
            except Exception as e:
                logger.exception("Unexpected error on row %s: %s", index, e)
                results["failed"].append({
                    "row": index,
                    "name": label,
                    "error": [str(e)],
                })

        if dry_run:
            results['summary'] = (
                f'Validation complete: {len(results["succeeded"])} rows valid, '
                f'{len(results["failed"])} rows have errors.'
            )
        else:
            results['summary'] = (
                f'{len(results["succeeded"])} imported, {len(results["failed"])} failed.'
            )

        return results
