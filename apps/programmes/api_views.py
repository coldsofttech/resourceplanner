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

from .models import Programme
from .serializers import (
    ProgrammeSerializer,
    ProgrammeExportSerializer,
    ProgrammeSummarySerializer,
)
from .services import ProgrammeService

logger = logging.getLogger(__name__)


class ProgrammeViewSet(viewsets.ViewSet):
    # GET /programmes/
    def list(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ProgrammeService.list_programmes(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ProgrammeSerializer(result["results"], many=True)
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

    # GET /programmes/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def statistics(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ProgrammeService.list_stats(fields=fields)
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

    # GET /programmes/options/
    @action(detail=False, methods=["get"], url_path="options")
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ProgrammeService.list_options(fields=fields)
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

    # GET /programmes/<id>/
    def retrieve(self, request, pk=None):
        try:
            programme = ProgrammeService.get_programme(pk)
            return Response(
                ProgrammeSerializer(programme).data, status=status.HTTP_200_OK
            )
        except Programme.DoesNotExist:
            logger.warning("Programme %s does not exist.", pk)
            return Response(
                {"error": "Programme not found."}, status=status.HTTP_404_NOT_FOUND
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

    # POST /programmes/
    def create(self, request):
        try:
            serializer = ProgrammeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            programme = ProgrammeService.create_programme(serializer.validated_data)
            return Response(
                ProgrammeSerializer(programme).data, status=status.HTTP_201_CREATED
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

    def _perform_update(self, request, pk, partial=False):
        try:
            try:
                instance = Programme.objects.get(pk=pk)
            except Programme.DoesNotExist:
                logger.warning("Programme %s does not exist.", pk)
                return Response(
                    {"error": "Programme not found."}, status=status.HTTP_404_NOT_FOUND
                )

            serializer = ProgrammeSerializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            updated = ProgrammeService.update_programme(pk, serializer.validated_data)
            return Response(
                ProgrammeSerializer(updated).data, status=status.HTTP_200_OK
            )
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

    # PUT /programmes/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /programmes/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /programmes/<id>/
    def destroy(self, request, pk=None):
        try:
            ProgrammeService.delete_programme(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Programme.DoesNotExist:
            logger.warning("Programme %s does not exist.", pk)
            return Response(
                {"error": "Programme not found."}, status=status.HTTP_404_NOT_FOUND
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

    # GET /programmes/<id>/summary/
    @action(detail=True, methods=["get"], url_path="summary")
    def programme_summary(self, request, pk=None):
        try:
            fy_param = request.query_params.get("fy")
            fy_id = None

            if fy_param is not None:
                try:
                    fy_id = int(fy_param)
                    if fy_id <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    return Response(
                        {
                            "error",
                            "Invalid 'fy' parameter. Must be a positive integer.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            result = ProgrammeService.get_programme_summary(pk, fy_id, page, page_size)
            serializer = ProgrammeSummarySerializer(result)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Programme.DoesNotExist:
            logger.warning("Programme %s does not exist.", pk)
            return Response(
                {"error": "Programme not found."}, status=status.HTTP_404_NOT_FOUND
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

    # GET /programmes/import/specifications/
    @action(detail=False, methods=["get"], url_path="import/specifications")
    def import_specifications(self, request):
        specs = {
            "fields": [
                {"name": "name", "required": True, "type": "string", "max_length": 100},
                {"name": "description", "required": False, "type": "string"},
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
                "'name' must be unique across all programmes.",
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /programmes/import/sample/
    @action(detail=False, methods=["get"], url_path="import/sample")
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "description", "is_active"])
        writer.writerow(
            [
                "Digital Transformation",
                "Modernisation of core business systems.",
                "true",
            ]
        )
        writer.writerow(
            [
                "Customer Experience",
                "Initiatives to improve customer touchpoints.",
                "true",
            ]
        )
        writer.writerow(
            ["Legacy Decommission", "Retirement of end-of-life platforms.", "false"]
        )
        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="programmes_import_template.csv"'
        )
        return response

    # POST /programmes/import/
    @action(detail=False, methods=["post"], url_path="import")
    def bulk_import(self, request):
        dry_run = request.query_params.get("validate", "false").lower() == "true"
        try:
            results = ProgrammeService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logger.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # GET /programmes/export/
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        try:
            qs = Programme.objects.all().order_by("name")
            data = ProgrammeExportSerializer(qs, many=True).data
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
