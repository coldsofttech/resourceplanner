import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .models import OfficeLocation

logger = logging.getLogger(__name__)


class OfficeLocationService:
    @staticmethod
    def _parse_bool(val):
        """
        Normalise 'true'/'True'/'false'/'False' to Python bool, or None if absent.
        """
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_locations(filters=None, page=1, page_size=20):
        """
        List the office locations.
        Supports filters: search, is_active
        """
        VALID_ORDER_FIELDS = {'city', 'country', 'is_active'}
        qs = OfficeLocation.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(city__icontains=s_term) | qs.filter(country__icontains=s_term)

            if filters.get('is_active') is not None:
                is_active_raw = filters['is_active']
                is_active = OfficeLocationService._parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'city'
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
        List the statistics of the office locations.
        Supports filters: fields
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = OfficeLocation.objects.all()
        result = {}

        if wants("total_locations"):
            result["total_locations"] = qs.count()
        if wants("active_locations"):
            result["active_locations"] = qs.filter(is_active=True).count()
        if wants("inactive_locations"):
            result["inactive_locations"] = qs.filter(is_active=False).count()

        return result

    @staticmethod
    def list_options(fields=None):
        """
        List the options available for fields of office locations.
        Supports filters: fields
        """

        def wants(field):
            return fields is None or field in fields

        ds = {
            "is_active": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
            "is_default": [
                {"value": True, "label": "Default"},
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
    def get_location(location_id: int):
        """
        Returns the details of the specified location id.
        """
        if not location_id:
            raise ValidationError("Invalid: location_id must be an integer and greater than 0.")

        return OfficeLocation.objects.get(pk=location_id)

    @staticmethod
    @transaction.atomic
    def create_location(data: dict):
        """
        Creates new location.
        """
        if not isinstance(data, dict) or 'city' not in data or 'country' not in data:
            raise ValidationError("Invalid: data must be a dictionary and 'city' and 'country' are required fields.")

        city = data['city'].strip()
        if not city:
            raise ValidationError("Invalid: city cannot be blank.")

        country = data['country'].strip()
        if not country:
            raise ValidationError("Invalid: country cannot be blank.")

        # Verify whether entry already exists
        if OfficeLocation.objects.filter(city=city, country=country).exists():
            raise ValidationError(f"Location '{city}, {country}' already exists.")

        # Create the location
        try:
            if data.get('is_default', False):
                OfficeLocation.objects.filter(is_default=True).update(is_default=False)

            location = OfficeLocation(
                city=city,
                country=country,
                is_active=data.get('is_active', True),
                is_default=data.get('is_default', False),
            )
            location.full_clean()
            location.save()
            return location
        except IntegrityError as e:
            logger.error("Database error when creating location '%s, %s': %s", city, country, e)
            raise ValidationError(f"Location '{city}, {country}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating location '%s, %s': %s", city, country, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating location '%s, %s': %s", city, country, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_location(location_id: int, data: dict):
        """
        Updates the specified location id.
        """
        if not location_id:
            raise ValidationError("Invalid: location_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        location = OfficeLocation.objects.get(pk=location_id)
        if not location:
            raise ValidationError(f"Location '{location_id}' does not exist.")

        if 'city' in data:
            new_city = data['city'].strip()
            if not new_city:
                raise ValidationError("Invalid: city cannot be blank.")
            if OfficeLocation.objects.filter(city=new_city, country=location.country).exclude(id=location_id).exists():
                raise ValidationError(f"Location '{new_city}, {location.country}' already exists.")
            location.city = new_city
        if 'country' in data:
            new_country = data['country'].strip()
            if not new_country:
                raise ValidationError("Invalid: country cannot be blank.")
            if OfficeLocation.objects.filter(country=new_country, city=location.city).exclude(id=location_id).exists():
                raise ValidationError(f"Location '{location.city}, {new_country}' already exists.")
            location.country = new_country
        if 'is_active' in data:
            location.is_active = data['is_active']
        if 'is_default' in data:
            if data['is_default']:
                OfficeLocation.objects.exclude(pk=location_id).filter(is_default=True).update(is_default=False)
            location.is_default = data['is_default']

        try:
            location.full_clean()
            location.save()
            return location
        except IntegrityError as e:
            logger.error("Database error when updating location '%s': %s", location_id, e)
            raise ValidationError(f"Location '{location_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating location '%s': %s", location_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating location '%s': %s", location_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_location(location_id: int):
        """
        Deletes the specified location id.
        """
        if not location_id:
            raise ValidationError("Invalid: location_id must be an integer and greater than 0.")

        location = OfficeLocation.objects.get(pk=location_id)
        if not location:
            raise ValidationError(f"Location '{location_id}' does not exist.")

        try:
            location.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting location '%s': %s", location_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting location '%s': %s", location_id, e)
            raise

    @staticmethod
    def list_members(location_id: int, page=1, page_size=20, include_inactive=False):
        """
        List all members associated with specified location
        """
        if not location_id:
            raise ValidationError("Invalid: location_id must be an integer and greater than 0.")

        location = OfficeLocation.objects.get(pk=location_id)
        if not location:
            raise ValidationError(f"Location '{location_id}' does not exist.")

        from apps.team_members.models import TeamMember
        if include_inactive:
            qs = TeamMember.objects.filter(
                location=location
            ).order_by('last_name', 'first_name')
        else:
            qs = TeamMember.objects.filter(
                is_active=True, location=location
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
        city = data.get('city', '').strip()
        if not city:
            raise ValidationError("'city' is required and cannot be blank.")
        if len(city) > 100:
            raise ValidationError("'city' must be 100 characters or fewer.")

        country = data.get('country', '').strip()
        if not country:
            raise ValidationError("'country' is required and cannot be blank.")
        if len(country) > 100:
            raise ValidationError("'country' must be 100 characters or fewer.")

        if OfficeLocation.objects.filter(city=city, country=country).exists():
            raise ValidationError(f"Location '{city}, {country}' already exists.")

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
            city = row.get('city', '').strip()
            country = row.get('country', '').strip()
            try:
                data = {
                    "city": city,
                    "country": country,
                    "is_active": (row.get('is_active') or 'true').strip().lower() == "true",
                }

                if dry_run:
                    # Validate only — no DB writes.
                    OfficeLocationService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": f"{city}, {country}"})
                else:
                    # Full import — _validate_row is also called inside create_location.
                    location = OfficeLocationService.create_location(data)
                    results["succeeded"].append({"row": index, "name": f"{city}, {country}"})
            except (ValidationError, ValueError, IntegrityError, DatabaseError, Exception) as e:
                results["failed"].append({
                    "row": index,
                    "name": f"{city}, {country}",
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
