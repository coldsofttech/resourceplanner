import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.core.utils import view_set_validation_details

from .models import Project
from .serializers import (
    ProjectSerializer,
    ProjectOperationalSerializer,
    ProjectTeamsSerializer,
    ProjectExportSerializer,
)
from .services import ProjectService

logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ViewSet):
    # GET /projects/
    def list(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ProjectService.list_projects(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ProjectSerializer(result["results"], many=True)
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

    # GET /projects/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def statistics(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ProjectService.list_stats(fields=fields)
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
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/options/
    @action(detail=False, methods=["get"], url_path="options")
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ProjectService.list_options(fields=fields)
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
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/
    def retrieve(self, request, pk=None):
        try:
            project = ProjectService.get_project(pk)
            return Response(ProjectSerializer(project).data, status=status.HTTP_200_OK)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in retrieve: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/operational/
    # PATCH /projects/<id>/operational/
    @action(detail=True, methods=["get", "patch"], url_path="operational")
    def operational(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project % does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                return Response(
                    ProjectOperationalSerializer(instance).data,
                    status=status.HTTP_200_OK,
                )

            serializer = ProjectOperationalSerializer(
                instance, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            operational_fields = {
                "efforts_issued",
                "effort_issue_commitment_date",
                "run_cost_applies",
            }
            filtered_data = {
                k: v
                for k, v in serializer.validated_data.items()
                if k in operational_fields
            }
            updated = ProjectService.update_project(
                pk, filtered_data, operational_only=True
            )
            return Response(
                ProjectOperationalSerializer(updated).data, status=status.HTTP_200_OK
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in operational: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in operational: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/teams/
    # PATCH /projects/<id>/teams/
    @action(detail=True, methods=["get", "patch"], url_path="teams")
    def teams(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project % does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                return Response(
                    ProjectTeamsSerializer(instance).data, status=status.HTTP_200_OK
                )

            updated = ProjectService.update_project_teams(pk, request.data)
            return Response(
                ProjectTeamsSerializer(updated).data, status=status.HTTP_200_OK
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in teams: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in teams: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /projects/
    def create(self, request):
        try:
            serializer = ProjectSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            project = ProjectService.create_project(serializer.validated_data)
            return Response(
                ProjectSerializer(project).data, status=status.HTTP_201_CREATED
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in create: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial=False):
        try:
            try:
                instance = Project.objects.get(pk=pk)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            serializer = ProjectSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated = ProjectService.update_project(pk, serializer.validated_data)
            return Response(ProjectSerializer(updated).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in update: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in update: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /projects/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /projects/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /projects/<id>/
    def destroy(self, request, pk=None):
        try:
            ProjectService.delete_project(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in destroy: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in destroy: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/export/
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        try:
            qs = (
                Project.objects.select_related(
                    "project_type", "programme", "sub_status"
                )
                .all()
                .order_by("name")
            )
            data = ProjectExportSerializer(qs, many=True).data
            return Response(
                {"count": len(data), "results": data}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
