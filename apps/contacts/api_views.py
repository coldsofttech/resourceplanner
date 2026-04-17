import csv
import io
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.core.utils import view_set_validation_details

from .models import Contact
from .serializers import (
    ContactSerializer,
    ContactExportSerializer,
    ContactSuggestSerializer,
)
from .services import ContactService

logger = logging.getLogger(__name__)


class ContactViewSet(viewsets.ViewSet):
    # GET /contacts/
    def list(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ContactService.list_contacts(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ContactSerializer(result["results"], many=True)
            return Response(
                {
                    "results": serializer.data,
                    "pagination": {
                        "total_count": result["total_count"],
                        "total_pages": result["total_pages"],
                        "current_page": result["current_page"],
                        "page_size": result["page_size"],
                        "has_next": result["has_next"],
                        "has_previous": result["has_previous"],
                    },
                },
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in list: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /contacts/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def statistics(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ContactService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("DatabaseError in stats: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in stats: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /contacts/options/
    @action(detail=False, methods=["get"], url_path="options")
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ContactService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("DatabaseError in option_choices: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in option_choices: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /contacts/<id>/
    def retrieve(self, request, pk=None):
        try:
            if pk.lower() == "suggest":
                return self.suggest(request)
            
            contact = ContactService.get_contact(pk)
            return Response(ContactSerializer(contact).data, status=status.HTTP_200_OK)
        except Contact.DoesNotExist:
            logger.warning("Contact %s does not exist.", pk)
            return Response(
                {"error": "Contact not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logger.warning("Validation error in retrieve: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in retrieve: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /contacts/
    def create(self, request):
        try:
            serializer = ContactSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            contact = ContactService.create_contact(serializer.validated_data)
            return Response(
                ContactSerializer(contact).data, status=status.HTTP_201_CREATED
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logger.warning("Validation error in create: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in create: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="suggest")
    def suggest(self, request):
        q = request.query_params.get("q", "")
        contacts = ContactService.suggest(q)
        return Response(ContactSuggestSerializer(contacts, many=True).data)

    def _perform_update(self, request, pk, partial=False):
        try:
            try:
                instance = Contact.objects.get(pk=pk)
            except Contact.DoesNotExist:
                logger.warning("Contact %s does not exist.", pk)
                return Response(
                    {"error": "Contact not found."}, status=status.HTTP_404_NOT_FOUND
                )
            
            is_active = request.data.get("is_active")
            self.reactivate(request, pk) if is_active else self.deactivate(request, pk)

            serializer = ContactSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated = ContactService.update_contact(pk, serializer.validated_data)
            return Response(ContactSerializer(updated).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logger.warning("Validation error in update: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in update: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in update: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /contacts/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /contacts/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /contacts/<id>/
    def destroy(self, request, pk=None):
        try:
            ContactService.delete_contact(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Contact.DoesNotExist:
            logger.warning("Contact %s does not exist.", pk)
            return Response(
                {"error": "Contact not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logger.warning("Validation error in destroy: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in destroy: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in destroy: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        reason = request.data.get("reason", "")
        try:
            ContactService.deactivate(pk, reason)
        except Contact.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "Contact deactivated."})

    @action(detail=False, methods=["patch"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        try:
            c = ContactService.reactivate(pk)
        except Contact.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response(ContactSerializer(c).data)

    # GET /contacts/import/specifications/
    @action(detail=False, methods=["get"], url_path="import/specifications")
    def import_specifications(self, request):
        specs = {
            "fields": [
                {
                    "name": "name",
                    "required": True,
                    "type": "string",
                    "max_length": 200,
                },
                {
                    "name": "email",
                    "required": True,
                    "type": "email",
                    "notes": "Must be unique across all contacts.",
                },
                {
                    "name": "is_active",
                    "required": False,
                    "type": "boolean",
                    "allowed_values": ["true", "false"],
                    "default": "true",
                },
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
                "'email' must be unique across all contacts.",
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /contacts/import/sample/
    @action(detail=False, methods=["get"], url_path="import/sample")
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "email", "is_active"])
        writer.writerow(["Alice Johnson", "alice.johnson@example.com", "true"])
        writer.writerow(["Bob Smith", "bob.smith@example.com", "true"])
        writer.writerow(["Carol White", "carol.white@example.com", "false"])
        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="contacts_import_template.csv"'
        )
        return response

    # POST /contacts/import/
    @action(detail=False, methods=["post"], url_path="import")
    def bulk_import(self, request):
        dry_run = request.query_params.get("validate", "false").lower() == "true"
        try:
            results = ContactService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logger.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # GET /contacts/export/
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        try:
            qs = Contact.objects.all().order_by("name")
            data = ContactExportSerializer(qs, many=True).data
            return Response(
                {"count": len(data), "results": data}, status=status.HTTP_200_OK
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in export: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
