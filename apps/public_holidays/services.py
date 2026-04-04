import csv
import datetime
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import PublicHoliday

logger = logging.getLogger(__name__)


class PublicHolidayService:
    @staticmethod
    def list_holidays(filters=None, page=1, page_size=20):
        """
        Return a paginated, filtered, ordered list of public holidays.

        Supported filter keys:
            search         — substring match on name or note
            location_id    — FK filter
            year           — filter by calendar year (integer)
            order_by       — field name (whitelist enforced)
            order_dir      — 'asc' | 'desc'
        """
        VALID_ORDER_FIELDS = {'date', 'name', 'location_id'}
        qs = PublicHoliday.objects.select_related('location').all()

        if filters:
            if filters.get('search'):
                term = filters['search']
                qs = qs.filter(name__icontains=term)

            if filters.get('location_id'):
                qs = qs.filter(location_id=filters['location_id'])

            if filters.get('year'):
                try:
                    qs = qs.filter(date__year=int(filters['year']))
                except (ValueError, TypeError):
                    pass

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'date'
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
        """
        Aggregate statistics for the list view stat cards.
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        from apps.office_locations.models import OfficeLocation

        qs = PublicHoliday.objects.all()
        result = {}

        if wants("total_holidays"):
            result["total_holidays"] = qs.count()
        if wants("total_locations"):
            result["total_locations"] = (
                OfficeLocation.objects.filter(is_active=True).count()
            )
        if wants("upcoming_holidays"):
            from django.utils import timezone
            today = timezone.localdate()
            result["upcoming_holidays"] = qs.filter(date__gte=today).count()

        return result

    @staticmethod
    def list_options(fields=None):
        """
        Return dropdown option lists needed by the list/form pages.
        """

        def wants(field):
            return fields is None or field in fields

        from apps.office_locations.models import OfficeLocation
        from django.db.models.functions import ExtractYear
        ds = {
            "locations": [
                {"value": location.pk, "label": f"{location.city}, {location.country}",
                 "is_default": location.is_default}
                for location in OfficeLocation.objects.filter(is_active=True)
            ],
            "years": [
                {"value": year, "label": str(year)}
                for year in PublicHoliday.objects.annotate(
                    yr=ExtractYear('date')
                ).order_by("-yr").values_list(
                    'yr', flat=True
                ).distinct()
            ]
        }
        result = {}

        if wants("locations"):
            result["locations"] = ds["locations"]
        if wants('years'):
            result["years"] = ds["years"]

        return result

    @staticmethod
    def get_holiday(holiday_id: int):
        """
        Returns the details of the specified id.
        """
        if not holiday_id:
            raise ValidationError("Invalid: holiday_id must be a positive integer.")

        return PublicHoliday.objects.select_related('location').get(pk=holiday_id)

    @staticmethod
    @transaction.atomic
    def create_holiday(data: dict):
        """
        Creates new holiday
        """
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        if PublicHoliday.objects.filter(
                location=data['location'],
                date=data['date'],
        ).exists():
            raise ValidationError(
                f"A public holiday for that location on {data['date']} already exists."
            )

        try:
            holiday = PublicHoliday(
                location=data['location'],
                date=data['date'],
                name=data['name'].strip(),
            )
            holiday.full_clean()
            holiday.save()
            return holiday
        except IntegrityError as e:
            logger.error("Database error when creating holiday '%s, %s': %s", data.get('location'), data.get('date'), e)
            raise ValidationError(
                f"A public holiday '{data.get('location')}, {data.get('date')}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating holiday '%s, %s': %s", data.get('location'),
                             data.get('date'), e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating holiday '%s, %s': %s", data.get('location'),
                             data.get('date'), e)
            raise

    @staticmethod
    @transaction.atomic
    def update_holiday(holiday_id: int, data: dict):
        """
        Updates the specified holiday id.
        """
        if not holiday_id:
            raise ValidationError("Invalid: holiday_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        holiday = PublicHoliday.objects.get(pk=holiday_id)
        if not holiday:
            raise ValidationError(f"A public holiday '{holiday_id}' does not exist.")

        location = data.get('location')
        date = data.get('date')
        if location and date and PublicHoliday.objects.filter(location=location, date=date).exclude(
                pk=holiday_id).exists():
            raise ValidationError(f"A public holiday '{location}, {date}' already exists.")

        if 'location' in data:
            holiday.location = data['location']
        if 'date' in data:
            holiday.date = data['date']
        if 'name' in data:
            holiday.name = data['name'].strip()

        try:
            holiday.full_clean()
            holiday.save()
            return holiday
        except IntegrityError as e:
            logger.error("Database error when updating holiday '%s': %s", holiday_id, e)
            raise ValidationError(f"A public holiday '{holiday_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating holiday '%s': %s", holiday_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating holiday '%s': %s", holiday_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_holiday(holiday_id: int):
        """
        Deletes the specified holiday id.
        """
        if not holiday_id:
            raise ValidationError("Invalid: holiday_id must be an integer and greater than 0.")

        holiday = PublicHoliday.objects.get(pk=holiday_id)
        if not holiday:
            raise ValidationError(f"A public holiday '{holiday_id}' does not exist.")

        try:
            holiday.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting holiday '%s': %s", holiday_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting holiday '%s': %s", holiday_id, e)
            raise

    @staticmethod
    def _resolve_lookups():
        """
        Build and return FK lookup caches in a single pass each.
        Called once per import, not once per row.
        """
        from apps.office_locations.models import OfficeLocation
        return {
            'location_map': {
                f"{loc.city.strip().lower()}|{loc.country.strip().lower()}": loc
                for loc in OfficeLocation.objects.all()
            },
            'existing_pairs': set(
                PublicHoliday.objects.values_list('location_id', 'date')
            ),
        }

    @staticmethod
    def _validate_row(row: dict, lookups: dict):
        """
        Validate a single import row without writing to the database.
        Raises ValidationError with a user-facing message on any failure.
        Used by both the dry-run path and the real import path.
        """
        errors = []

        date = row.get('date', '').strip()
        name = row.get('name', '').strip()

        if not date: errors.append("'date' is required.")
        if not name: errors.append("'name' is required.")

        city_raw = row.get('city', '').strip()
        country_raw = row.get('country', '').strip()

        location_key = f"{city_raw.lower()}|{country_raw.lower()}" if city_raw and country_raw else ''
        location_obj = lookups['location_map'].get(location_key) if location_key else None

        if not city_raw or not country_raw:
            errors.append("'city' and 'country' are both required.")
        elif location_obj is None:
            errors.append(f"Location '{city_raw}, {country_raw}' not found.")

        date_obj = None
        if date:
            try:
                date_obj = datetime.date.fromisoformat(date)
            except ValueError:
                errors.append(f"'date' must be in YYYY-MM-DD format, got '{date}'.")

        if location_obj and date_obj:
            pair = (location_obj.pk, date_obj)
            if pair in lookups['existing_pairs']:
                errors.append(
                    f"A holiday for {city_raw}, {country_raw} on {date} already exists."
                )

        if errors:
            raise ValidationError(errors)

        return {
            "location": location_obj,
            "date": date_obj,
            "name": name,
        }

    @staticmethod
    def bulk_import(request, dry_run=False):
        file = request.FILES.get('file')
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith('.csv'):
            raise ValidationError("Only CSV files are supported.")

        try:
            decoded = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError:
            logger.warning("Unicode error when reading import file.")
            raise ValidationError("File must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error reading import file: %s", e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"Maximum {MAX_ROWS} rows allowed per import.")

        REQUIRED_HEADERS = {'city', 'country', 'date', 'name'}
        actual_headers = set(reader.fieldnames or [])
        missing = REQUIRED_HEADERS - actual_headers
        if missing:
            raise ValidationError(f"Missing required columns: {', '.join(sorted(missing))}")

        lookups = PublicHolidayService._resolve_lookups()

        results = {
            "succeeded": [],
            "failed": [],
            "total": len(rows),
            "dry_run": dry_run,
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):  # start=2 accounts for header row
            label = f"{row.get('name', '').strip()} ({row.get('date', '').strip()})"
            try:
                cleaned = PublicHolidayService._validate_row(row, lookups)

                if dry_run:
                    results["succeeded"].append({"row": index, "name": label})
                else:
                    holiday = PublicHoliday.objects.create(**cleaned)
                    # Prevent intra-file duplicates
                    lookups["existing_pairs"].add((holiday.location.pk, holiday.date))
                    results["succeeded"].append({"row": index, "name": str(holiday)})
            except ValidationError as e:
                results["failed"].append({
                    "row": index,
                    "name": label,
                    "error": e.messages if hasattr(e, 'messages') else [str(e)],
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

        results["summary"] = (
            f"Validation complete: {len(results['succeeded'])} rows valid, "
            f"{len(results['failed'])} rows have errors."
            if dry_run else
            f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
        )

        return results
