import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.core.utils import view_set_validation_details

from .models import Project, ProjectBudget, ProjectEstimate, ProjectLabel
from .serializers import (
    ProjectBudgetHistorySerializer,
    ProjectBudgetLifetimeSerializer,
    ProjectBudgetSerializer,
    ProjectCodeSerializer,
    ProjectCommentSerializer,
    ProjectEstimateHistorySerializer,
    ProjectEstimateSerializer,
    ProjectLabelSerializer,
    ProjectSerializer,
    ProjectOperationalSerializer,
    ProjectStatusHistorySerializer,
    ProjectTagSerializer,
    ProjectTeamsSerializer,
    ProjectExportSerializer,
)
from .services import (
    ProjectBudgetService,
    ProjectCodeService,
    ProjectCommentService,
    ProjectEstimateService,
    ProjectLabelService,
    ProjectService,
    ProjectStatusHistoryService,
    ProjectTagService,
)

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
            code = (request.data.get("code") or "").strip()
            project = ProjectService.create_project(
                serializer.validated_data, code=code
            )
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

    # GET /projects/<id>/labels/
    # POST /projects/<id>/labels/
    @action(detail=True, methods=["get", "post"], url_path="labels")
    def labels_create_or_get(self, request, pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                result = ProjectLabelService.list_labels_for_project(
                    instance, page, page_size
                )
                serializer = ProjectLabelSerializer(result["results"], many=True)
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

            if request.method == "POST":
                label_val = request.data.get("label") or None
                is_primary = bool(request.data.get("is_primary", False))
                label = ProjectLabelService.create_label(
                    instance, label_val, is_primary
                )
                return Response(
                    ProjectLabelSerializer(label).data, status=status.HTTP_201_CREATED
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
            logger.exception("DatabaseError in labels_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in labels_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/labels/suggest/
    @action(detail=True, methods=["get"], url_path="labels/suggest")
    def label_suggest(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            suggestion = ProjectLabelService.suggest_label(instance)
            return Response({"suggestion": suggestion}, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in label_suggest: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in label_suggest: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/labels/<id>/
    # PATCH /projects/<id>/labels/<id>/
    # DELETE /projects/<id>/labels/<id>/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="labels/(?P<label_pk>[^/.]+)",
    )
    def labels_get_patch_or_delete(self, request, pk=None, label_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                label = ProjectLabelService.get_label(instance, label_pk)
                return Response(
                    ProjectLabelSerializer(label).data, status=status.HTTP_200_OK
                )

            try:
                label = ProjectLabelService.get_label(instance, label_pk)
            except ProjectLabel.DoesNotExist:
                logger.warning("Project label %s does not exist.", label_pk)
                return Response(
                    {"error": "Project label not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if request.method == "PATCH":
                updated = ProjectLabelService.update_label(
                    instance, label_pk, **request.data
                )
                return Response(
                    ProjectLabelSerializer(updated).data, status=status.HTTP_200_OK
                )

            if request.method == "DELETE":
                ProjectLabelService.delete_label(instance, label_pk)
                return Response(status=status.HTTP_204_NO_CONTENT)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in labels_get_patch_or_delete: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in labels_get_patch_or_delete: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/status/history/
    @action(detail=True, methods=["get"], url_path="status/history")
    def status_history(self, request, pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            result = ProjectStatusHistoryService.list_history_for_project(
                instance, page, page_size
            )
            serializer = ProjectStatusHistorySerializer(result["results"], many=True)
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
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in status history: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in status history: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/tags/
    # POST /projects/<id>/tags/
    @action(detail=True, methods=["get", "post"], url_path="tags")
    def tags_create_or_get(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                result = ProjectTagService.list_tags_for_project(pk)
                serializer = ProjectTagSerializer(result, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            if request.method == "POST":
                name = (request.data.get("name") or "").strip()
                if not name:
                    return Response(
                        {"details": {"name": ["Tag name is required."]}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                pt = ProjectTagService.add_tag(pk, name)
                return Response(
                    ProjectTagSerializer(pt).data, status=status.HTTP_201_CREATED
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
            logger.exception("DatabaseError in tags_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in tags_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # DELETE /projects/<id>/tags/<id>/
    @action(detail=True, methods=["delete"], url_path="tags/(?P<tag_pk>[^/.]+)")
    def tags_delete(self, request, pk=None, tag_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "DELETE":
                ProjectTagService.remove_tag(pk, tag_pk)
                return Response(status=status.HTTP_204_NO_CONTENT)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in tags_delete: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in tags_delete: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/comments/
    # POST /projects/<id>/comments/
    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments_create_or_get(self, request, pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                result = ProjectCommentService.list_for_project(pk, page, page_size)
                result["pinned"] = ProjectCommentSerializer(
                    result["pinned"], many=True
                ).data
                result["results"] = ProjectCommentSerializer(
                    result["results"], many=True
                ).data
                return Response(result, status=status.HTTP_200_OK)

            if request.method == "POST":
                comment_text = (request.data.get("comment") or "").strip()
                comment = ProjectCommentService.create_comment(pk, comment_text)
                return Response(
                    ProjectCommentSerializer(comment).data,
                    status=status.HTTP_201_CREATED,
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
            logger.exception("DatabaseError in comments_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in comments_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PATCH /projects/<id>/comments/<id>/
    # DELETE /projects/<id>/comments/<id>/
    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path="comments/(?P<comment_pk>[^/.]+)",
    )
    def comments_patch_or_delete(self, request, pk=None, comment_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "PATCH":
                comment = ProjectCommentService.update_comment(comment_pk, request.data)
                return Response(
                    ProjectCommentSerializer(comment).data, status=status.HTTP_200_OK
                )

            if request.method == "DELETE":
                ProjectCommentService.delete_comment(comment_pk)
                return Response(status=status.HTTP_204_NO_CONTENT)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in comments_patch_or_delete: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in comments_patch_or_delete: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/codes/
    # POST /projects/<id>/codes/
    @action(detail=True, methods=["get", "post"], url_path="codes")
    def codes_create_or_get(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                active_code = ProjectCodeService.get_active(instance.pk)
                if active_code is None:
                    return Response(
                        {"id": None, "code": None, "notes": None, "created_at": None},
                        status=status.HTTP_204_NO_CONTENT,
                    )
                return Response(
                    ProjectCodeSerializer(active_code).data, status=status.HTTP_200_OK
                )

            if request.method == "POST":
                serializer = ProjectCodeSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                code_entry = ProjectCodeService.set_code(
                    instance.pk,
                    serializer.validated_data["code"],
                    serializer.validated_data.get("notes") or None,
                )
                return Response(
                    ProjectCodeSerializer(code_entry).data,
                    status=status.HTTP_201_CREATED,
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
            logger.exception("DatabaseError in codes_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in codes_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/codes/history/
    @action(detail=True, methods=["get"], url_path="codes/history")
    def codes_history(self, request, pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            result = ProjectCodeService.get_history(instance.pk, page, page_size)
            serializer = ProjectCodeSerializer(result["results"], many=True)
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
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in codes_history: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in codes_history: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/estimates/
    # POST /projects/<id>/estimates/
    @action(detail=True, methods=["get", "post"], url_path="estimates")
    def estimates_create_or_get(self, request, pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                result = ProjectEstimateService.list_estimates(
                    instance.pk, page, page_size
                )
                serializer = ProjectEstimateSerializer(result["results"], many=True)
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

            if request.method == "POST":
                notes = request.data.get("notes") or ""
                estimate = ProjectEstimateService.create_estimate(
                    instance.pk, request.data, notes
                )
                return Response(
                    ProjectEstimateSerializer(estimate).data,
                    status=status.HTTP_201_CREATED,
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
            logger.exception("DatabaseError in estimates_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in estimates_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/estimates/<id>/
    # PATCH /projects/<id>/estimates/<id>/
    # DELETE /projects/<id>/estimates/<id>/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="estimates/(?P<estimate_pk>[^/.]+)",
    )
    def estimates_patch_delete_or_get(self, request, pk=None, estimate_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                estimate = ProjectEstimateService.get_estimate(pk, estimate_pk)
                return Response(
                    ProjectEstimateSerializer(estimate).data, status=status.HTTP_200_OK
                )

            if request.method == "PATCH":
                notes = request.data.get("notes") or ""
                estimate = ProjectEstimateService.update_estimate(
                    pk, estimate_pk, request.data, notes
                )
                return Response(
                    ProjectEstimateSerializer(estimate).data, status=status.HTTP_200_OK
                )

            if request.method == "DELETE":
                ProjectEstimateService.delete_estimate(pk, estimate_pk)
                return Response(status=status.HTTP_204_NO_CONTENT)
        except (ValueError, ProjectEstimate.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in estimates_patch_delete_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in estimates_patch_delete_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/estimates/options/
    @action(detail=True, methods=["get"], url_path="estimates/options")
    def estimates_option_choices(self, request, pk=None):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ProjectEstimateService.list_options(pk, fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("DatabaseError in estimates_option_choices: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in estimates_option_choices: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/estimates/<id>/history/
    @action(
        detail=True,
        methods=["get"],
        url_path="estimates/(?P<estimate_pk>[^/.]+)/history",
    )
    def estimates_history(self, request, pk=None, estimate_pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                project_instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            try:
                estimate_instance = ProjectEstimateService.get_estimate(pk, estimate_pk)
            except ProjectEstimate.DoesNotExist:
                logger.warning("Project estimate %s does not exist.", estimate_pk)
                return Response(
                    {"error": "Project estimate not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            result = ProjectEstimateService.list_history(
                pk, estimate_pk, page, page_size
            )
            serializer = ProjectEstimateHistorySerializer(result["results"], many=True)
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
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in estimates_history: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in estimates_history: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/budgets/
    # POST /projects/<id>/budgets/
    @action(detail=True, methods=["get", "post"], url_path="budgets")
    def budget_create_or_get(self, request, pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                result = ProjectBudgetService.list_for_project(pk)
                serializer = ProjectBudgetSerializer(result, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)

            if request.method == "POST":
                budget = ProjectBudgetService.create_budget(
                    project_id=pk,
                    financial_year_id=request.data.get("financial_year"),
                    allocated_budget=request.data.get("allocated_budget") or None,
                    refined_budget=request.data.get("refined_budget") or None,
                    estimate_version_id=request.data.get("estimate_version") or None,
                    notes=request.data.get("notes") or None,
                )
                return Response(
                    ProjectBudgetSerializer(budget).data, status=status.HTTP_201_CREATED
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
            logger.exception("DatabaseError in budget_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in budget_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/budgets/<id>/
    # PATCH /projects/<id>/budgets/<id>/
    # DELETE /projects/<id>/budgets/<id>/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path=r"budgets/(?P<budget_pk>(?!lifetime)[^/.]+)",
    )
    def budget_patch_delete_or_get(self, request, pk=None, budget_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                budget = ProjectBudgetService.get_budget(pk, budget_pk)
                return Response(
                    ProjectBudgetSerializer(budget).data, status=status.HTTP_200_OK
                )

            if request.method == "PATCH":
                kwargs = {}
                if "allocated_budget" in request.data:
                    kwargs["allocated_budget"] = (
                        request.data["allocated_budget"] or None
                    )
                if "refined_budget" in request.data:
                    kwargs["refined_budget"] = request.data["refined_budget"] or None
                if "estimate_version" in request.data:
                    kwargs["estimate_version_id"] = (
                        request.data["estimate_version"] or None
                    )
                if "notes" in request.data:
                    kwargs["notes"] = request.data["notes"] or None

                budget = ProjectBudgetService.update_budget(pk, budget_pk, **kwargs)
                return Response(
                    ProjectBudgetSerializer(budget).data, status=status.HTTP_200_OK
                )

            if request.method == "DELETE":
                ProjectBudgetService.delete_budget(pk, budget_pk)
                return Response(status=status.HTTP_204_NO_CONTENT)
        except (ValueError, ProjectEstimate.DoesNotExist) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in budget_patch_delete_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in budget_patch_delete_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/budgets/<pk>/history/
    @action(
        detail=True,
        methods=["get"],
        url_path=r"budgets/(?P<budget_pk>(?!lifetime)[^/.]+)/history",
    )
    def budgets_history(self, request, pk=None, budget_pk=None):
        try:
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            try:
                project_instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            try:
                budget_instance = ProjectBudgetService.get_budget(pk, budget_pk)
            except ProjectBudget.DoesNotExist:
                logger.warning("Project budget %s does not exist.", budget_pk)
                return Response(
                    {"error": "Project budget not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            result = ProjectBudgetService.list_history(pk, budget_pk, page, page_size)
            serializer = ProjectBudgetHistorySerializer(result["results"], many=True)
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
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {
                    "error": "Invalid parameters.",
                    "details": view_set_validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DatabaseError in budgets_history: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in budgets_history: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/budgets/lifetime/
    @action(detail=True, methods=["get"], url_path="budgets/lifetime")
    def budgets_lifetime(self, request, pk=None):
        try:
            try:
                project_instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            result = ProjectBudgetService.lifetime_budget(pk)
            return Response(
                ProjectBudgetLifetimeSerializer(result).data, status=status.HTTP_200_OK
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
            logger.exception("DatabaseError in budgets_lifetime: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in budgets_lifetime: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
