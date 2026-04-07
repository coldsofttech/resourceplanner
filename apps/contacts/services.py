import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.validators import validate_email
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Q

from apps.core.utils import parse_bool

from .models import Contact

logger = logging.getLogger(__name__)


class ContactService:

    @staticmethod
    def list_contacts(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {"name", "email", "is_active"}
        qs = Contact.objects.all()

        if filters:
            if filters.get("search"):
                s_term = filters["search"]
                qs = qs.filter(Q(name__icontains=s_term) | Q(email__icontains=s_term))
            if filters.get("is_active") is not None and filters.get("is_active") != "":
                is_active = parse_bool(filters["is_active"])
                qs = qs.filter(is_active=is_active)

        order_by = filters.get("order_by") if filters else None
        order_dir = filters.get("order_dir") if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else "name"
        if order_dir == "desc":
            order_field = f"-{order_field}"
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

        qs = Contact.objects.all()
        result = {}

        if wants("total_contacts"):
            result["total_contacts"] = qs.count()
        if wants("active_contacts"):
            result["active_contacts"] = qs.filter(is_active=True).count()
        if wants("inactive_contacts"):
            result["inactive_contacts"] = qs.filter(is_active=False).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        result = {}

        if wants("is_active"):
            result["is_active"] = [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]

        return result

    @staticmethod
    def get_contact(contact_id: int):
        if not contact_id:
            raise ValidationError("Invalid: contact_id must be a positive integer.")
        return Contact.objects.get(pk=contact_id)

    @staticmethod
    @transaction.atomic
    def create_contact(data: dict):
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dict.")

        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")

        email = (data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("'email' is required and cannot be blank.")

        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError(f"'{email}' is not a valid email address.")

        if Contact.objects.filter(email=email).exists():
            raise ValidationError(f"A contact with email '{email}' already exists.")

        try:
            contact = Contact(
                name=name,
                email=email,
                is_active=data.get("is_active", True),
            )
            contact.full_clean()
            contact.save()
            return contact
        except IntegrityError as e:
            logger.error("IntegrityError creating contact '%s': %s", email, e)
            raise ValidationError(
                f"Contact with email '{email}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating contact '%s': %s", email, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating contact '%s': %s", email, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_contact(contact_id: int, data: dict):
        if not contact_id:
            raise ValidationError("Invalid: contact_id must be a positive integer.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        contact = Contact.objects.get(pk=contact_id)
        if not contact:
            raise ValidationError(f"Contact '{contact_id}' does not exist.")

        if "name" in data:
            new_name = (data["name"] or "").strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            contact.name = new_name

        if "email" in data:
            new_email = (data["email"] or "").strip().lower()
            if not new_email:
                raise ValidationError("Invalid: email cannot be blank.")
            try:
                validate_email(new_email)
            except ValidationError:
                raise ValidationError(f"'{new_email}' is not a valid email address.")
            if Contact.objects.filter(email=new_email).exclude(pk=contact_id).exists():
                raise ValidationError(
                    f"A contact with email '{new_email}' already exists."
                )
            contact.email = new_email

        if "is_active" in data:
            contact.is_active = data["is_active"]

        try:
            contact.full_clean()
            contact.save()
            return contact
        except IntegrityError as e:
            logger.error("IntegrityError updating contact %s: %s", contact_id, e)
            raise ValidationError(
                "Contact could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating contact %s: %s", contact_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating contact '%s': %s", contact_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_contact(contact_id: int):
        if not contact_id:
            raise ValidationError("Invalid: contact_id must be a positive integer.")

        contact = Contact.objects.get(pk=contact_id)
        if not contact:
            raise ValidationError(f"Contact '{contact_id}' does not exist.")

        try:
            contact.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting contact %s: %s", contact_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting contact '%s': %s", contact_id, e
            )
            raise

    @staticmethod
    def _validate_row(data: dict):
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")
        if len(name) > 200:
            raise ValidationError("'name' must be 200 characters or fewer.")

        email = (data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("'email' is required and cannot be blank.")

        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError(f"'{email}' is not a valid email address.")

        if Contact.objects.filter(email=email).exists():
            raise ValidationError(f"A contact with email '{email}' already exists.")

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
            logger.warning("Unicode error reading import file.")
            raise ValidationError("File must be UTF-8 encoded.")
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

        for index, row in enumerate(rows, start=2):  # start=2 accounts for header row
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip().lower()
            label = email or name or f"(row {index})"

            try:
                data = {
                    "name": name,
                    "email": email,
                    "is_active": (row.get("is_active") or "true").strip().lower()
                    == "true",
                }

                if dry_run:
                    ContactService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": label})
                else:
                    ContactService.create_contact(data)
                    results["succeeded"].append({"row": index, "name": label})
            except (
                ValidationError,
                ValueError,
                IntegrityError,
                DatabaseError,
                Exception,
            ) as e:
                results["failed"].append(
                    {
                        "row": index,
                        "name": label,
                        "error": e.messages if hasattr(e, "messages") else str(e),
                    }
                )

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
