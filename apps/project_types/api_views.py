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

from .models import ProjectType
from .serializers import ProjectTypeSerializer, ProjectTypeExportSerializer
from .services import ProjectTypeService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class ProjectTypeViewSet(viewsets.ViewSet):
    # GET /project-types/
    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ProjectTypeService.list_types(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ProjectTypeSerializer(result["results"], many=True)
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
            logging.exception("Database error in list: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /project-types/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = ProjectTypeService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logging.exception("Database error in stats: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in stats: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /project-types/<id>/
    def retrieve(self, request, pk=None):
        try:
            _type = ProjectTypeService.get_type(pk)
            serializer = ProjectTypeSerializer(_type)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except ProjectType.DoesNotExist:
            logging.warning("Project type %s does not exist", pk)
            return Response(
                {
                    "error": "Project type not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in retrieve: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in retrieve: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /project-types/
    def create(self, request):
        try:
            serializer = ProjectTypeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            _type = ProjectTypeService.create_type(serializer.validated_data)
            return Response(
                ProjectTypeSerializer(_type).data,
                status=status.HTTP_201_CREATED,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in create: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in create: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        try:
            try:
                instance = ProjectType.objects.get(pk=pk)
            except ProjectType.DoesNotExist:
                logging.warning("Project type %s does not exist", pk)
                return Response(
                    {
                        "error": "Project type not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = ProjectTypeSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            _type = ProjectTypeService.update_type(pk, serializer.validated_data)
            return Response(
                ProjectTypeSerializer(_type).data,
                status=status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in _perform_update: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in _perform_update: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in _perform_update: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /project-types/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /project-types/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /project-types/<id>/
    def destroy(self, request, pk=None):
        try:
            ProjectTypeService.delete_type(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectType.DoesNotExist:
            logging.warning("Project type %s does not exist", pk)
            return Response(
                {
                    "error": "Project type not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in destroy: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in destroy: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in destroy: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /project-types/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        specs = {
            "fields": [
                {"name": "name", "required": True, "type": "string", "max_length": 60},
                {"name": "description", "required": False, "type": "string"},
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
            ]
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /project-types/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "description"])  # header
        writer.writerow(["Project", "Portfolio Projects"])  # sample row
        writer.writerow(["Maintenance", "Maintenance Projects"])  # sample row

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="project_types_import_template.csv"'
        return response

    # POST /project-types/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = ProjectTypeService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /project-types/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        try:
            qs = ProjectType.objects.all()
            data = ProjectTypeExportSerializer(qs, many=True).data
            return Response(
                {
                    "count": len(data),
                    "results": data,
                },
                status=status.HTTP_200_OK
            )
        except DatabaseError as e:
            logging.exception("Database error in export: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
