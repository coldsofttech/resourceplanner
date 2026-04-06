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

from .models import ProjectSubStatus
from .serializers import ProjectSubStatusSerializer, ProjectSubStatusExportSerializer
from .services import ProjectSubStatusService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class ProjectSubStatusViewSet(viewsets.ViewSet):
    # GET /project-sub-statuses/
    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ProjectSubStatusService.list_statuses(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ProjectSubStatusSerializer(result["results"], many=True)
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

    # GET /project-sub-statuses/<main_status>/
    @action(detail=False, methods=['get'], url_path=r'(?P<main_status>NEW|IN_PROGRESS|ON_HOLD|COMPLETED|CANCELLED)')
    def list_by_main_status(self, request, main_status=None):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            filters = request.query_params.dict()
            filters['main_status'] = main_status
            result = ProjectSubStatusService.list_statuses(
                filters=filters,
                page=page,
                page_size=page_size,
            )
            serializer = ProjectSubStatusSerializer(result["results"], many=True)
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

    # GET /project-sub-statuses/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            main_status = request.query_params.get("main_status")
            result = ProjectSubStatusService.list_options(fields=fields, main_status=main_status)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logging.exception("Database error in option_choices: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in option_choices: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /project-sub-statuses/<id>/
    def retrieve(self, request, pk=None):
        try:
            project_status = ProjectSubStatusService.get_status(pk)
            serializer = ProjectSubStatusSerializer(project_status)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except ProjectSubStatus.DoesNotExist:
            logging.warning("Project sub status %s does not exist", pk)
            return Response(
                {
                    "error": "Project sub status not found."
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

    # POST /project-sub-statuses/
    def create(self, request):
        try:
            serializer = ProjectSubStatusSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            project_status = ProjectSubStatusService.create_status(serializer.validated_data)
            return Response(
                ProjectSubStatusSerializer(project_status).data,
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
                instance = ProjectSubStatus.objects.get(pk=pk)
            except ProjectSubStatus.DoesNotExist:
                logging.warning("Project sub status %s does not exist", pk)
                return Response(
                    {
                        "error": "Project sub status not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = ProjectSubStatusSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            project_status = ProjectSubStatusService.update_status(pk, serializer.validated_data)
            return Response(
                ProjectSubStatusSerializer(project_status).data,
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

    # PUT /project-sub-statuses/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /project-sub-statuses/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /project-sub-statuses/<id>/
    def destroy(self, request, pk=None):
        try:
            ProjectSubStatusService.delete_status(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectSubStatus.DoesNotExist:
            logging.warning("Project sub status %s does not exist", pk)
            return Response(
                {
                    "error": "Project sub status not found."
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

    # POST /project-sub-statuses/<id>/reorder/
    @action(detail=True, methods=["post"], url_path="reorder")
    def reorder(self, request, pk=None):
        try:
            direction = request.data.get("direction", "")
            results = ProjectSubStatusService.reorder(pk, direction)
            return Response(ProjectSubStatusSerializer(results).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in reorder: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in reorder: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /project-sub-statuses/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        specs = {
            "fields": [
                {"name": "name", "required": True, "type": "string", "max_length": 100},
                {
                    "name": "main_status", "required": True, "type": "string", "max_length": 20,
                    "allowed_values": ProjectSubStatusService.MAIN_STATUSES
                },
                {
                    "name": "order", "required": False, "type": "integer",
                    "notes": "Omit or set to 0 to append at end of group."
                },
                {
                    "name": "is_active", "required": False, "type": "boolean",
                    "allowed_values": ["true", "false"], "default": "true"
                },
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
            ]
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /project-sub-statuses/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "main_status", "order", "is_active"])  # header
        writer.writerow(["Under Review", "NEW", 2, "true"])  # explicit order
        writer.writerow(["Estimates Shared", "NEW", 0, "true"])  # 0 = append to end
        writer.writerow(["In Progress", "IN_PROGRESS", 1, "true"])
        writer.writerow(["Blocked", "IN_PROGRESS", 0, "false"])  # inactive example

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="project_sub_statuses_import_template.csv"'
        return response

    # POST /project-sub-statuses/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = ProjectSubStatusService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /project-sub-statuses/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        try:
            qs = ProjectSubStatus.objects.all()
            data = ProjectSubStatusExportSerializer(qs, many=True).data
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
