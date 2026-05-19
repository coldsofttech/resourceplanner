import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from apps.core.utils import view_set_validation_details

from .models import (
    Project,
    ProjectAttachment,
    ProjectBudget,
    ProjectComment,
    ProjectCommentAttachment,
    ProjectContact,
    ProjectEstimate,
    ProjectFollower,
    ProjectLabel,
    ProjectLink,
    ProjectView,
)
from .serializers import (
    ProjectAttachmentSerializer,
    ProjectBudgetHistorySerializer,
    ProjectBudgetLifetimeSerializer,
    ProjectBudgetSerializer,
    ProjectCodeSerializer,
    ProjectCommentSerializer,
    ProjectContactArchiveSerializer,
    ProjectContactHistorySerializer,
    ProjectContactReadSerializer,
    ProjectContactWriteSerializer,
    ProjectEstimateHistorySerializer,
    ProjectEstimateSerializer,
    ProjectLabelSerializer,
    ProjectLinkSerializer,
    ProjectLinkWriteSerializer,
    ProjectSerializer,
    ProjectOperationalSerializer,
    ProjectStatusHistorySerializer,
    ProjectTagSerializer,
    ProjectTeamsSerializer,
    ProjectExportSerializer,
    ProjectViewSerializer,
)
from .services import (
    ProjectAttachmentService,
    ProjectBudgetService,
    ProjectCodeService,
    ProjectCommentService,
    ProjectContactService,
    ProjectEstimateService,
    ProjectLabelService,
    ProjectLinkService,
    ProjectService,
    ProjectStatusHistoryService,
    ProjectTagService,
    ProjectViewService,
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
                pk, filtered_data, operational_only=True, user=request.user
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

            updated = ProjectService.update_project_teams(pk, request.data, user=request.user)
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
            updated = ProjectService.update_project(pk, serializer.validated_data, user=request.user)
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
                mentioned_ids = request.data.get("mentioned_user_ids") or []
                comment = ProjectCommentService.create_comment(pk, comment_text, user=request.user, mentioned_user_ids=mentioned_ids)
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
                comment = ProjectCommentService.update_comment(comment_pk, request.data, user=request.user)
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
                    user=request.user,
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

    # POST /projects/<id>/estimates/<id>/send-approval-email/
    @action(
        detail=True,
        methods=["post"],
        url_path="estimates/(?P<estimate_pk>[^/.]+)/send-approval-email",
    )
    def estimates_send_approval_email(self, request, pk=None, estimate_pk=None):
        try:
            project = ProjectService.get_project(pk)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            estimate = ProjectEstimateService.get_estimate(pk, estimate_pk)
        except ProjectEstimate.DoesNotExist:
            return Response({"error": "Estimate not found."}, status=status.HTTP_404_NOT_FOUND)

        if estimate.status != ProjectEstimate.STATUS_APPROVED:
            return Response(
                {"error": "Only approved estimates can trigger an approval email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if project.status != Project.STATUS_IN_PROGRESS:
            return Response(
                {"error": "The project must be In Progress to send an approval email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from .email_service import ProjectApprovalEmailService
            ProjectEstimate.objects.filter(pk=estimate.pk).update(approval_email_sent=False)
            ProjectApprovalEmailService.send(project, estimate)
            ProjectEstimate.objects.filter(pk=estimate.pk).update(approval_email_sent=True)
            return Response({"detail": "Approval email sent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error sending approval email for project %s estimate %s: %s", pk, estimate_pk, e)
            return Response({"error": "Failed to send approval email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST /projects/<id>/toggle-follow/
    @action(detail=True, methods=["post"], url_path="toggle-follow")
    def toggle_follow(self, request, pk=None):
        try:
            project = ProjectService.get_project(pk)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        follower, created = ProjectFollower.objects.get_or_create(
            project=project, user=request.user
        )
        if not created:
            follower.delete()
            return Response({"is_following": False})
        return Response({"is_following": True})

    # GET /projects/<id>/follow-status/
    @action(detail=True, methods=["get"], url_path="follow-status")
    def follow_status(self, request, pk=None):
        is_following = ProjectFollower.objects.filter(
            project_id=pk, user=request.user
        ).exists()
        return Response({"is_following": is_following})

    # POST /projects/<id>/comments/upload-image/
    @action(
        detail=True, methods=["post"],
        url_path="comments/upload-image",
        parser_classes=[MultiPartParser, FormParser],
    )
    def comments_upload_image(self, request, pk=None):
        try:
            project = ProjectService.get_project(pk)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get('image')
        if not file_obj:
            return Response({"error": "No image uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        import base64
        content_type = getattr(file_obj, "content_type", "image/png") or "image/png"
        if file_obj.size > 10 * 1024 * 1024:
            return Response({"error": "Image exceeds 10 MB limit."}, status=status.HTTP_400_BAD_REQUEST)
        raw = file_obj.read()
        b64 = base64.b64encode(raw).decode("ascii")
        data_uri = f"data:{content_type};base64,{b64}"
        return Response({"url": data_uri}, status=status.HTTP_201_CREATED)

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

    # GET /projects/<id>/contacts/
    # POST /projects/<id>/contacts/
    @action(detail=True, methods=["get", "post"], url_path="contacts")
    def contacts_create_or_get(self, request, pk=None):
        if request.method == "GET":
            role = request.query_params.get("role")
            active_only = request.query_params.get("active", "1") != "0"
            if active_only:
                rows = ProjectContactService.list_active_for_project(pk, role)
            else:
                rows = ProjectContactService.list_for_project(pk, role)
            return Response(ProjectContactReadSerializer(rows, many=True).data)

        if request.method == "POST":
            ser = ProjectContactWriteSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            d = ser.validated_data
            try:
                pc = ProjectContactService.add(
                    project_id=pk,
                    role=d["role"],
                    contact_id=d.get("contact_id"),
                    name=d.get("name", ""),
                    email=d.get("email", ""),
                )
            except Exception as e:
                return Response({"detail": str(e)}, status=400)
            return Response(
                ProjectContactReadSerializer(pc).data,
                status=status.HTTP_201_CREATED,
            )

    # GET /projects/<id>/contacts/<id>/
    # PATCH /projects/<id>/contacts/<id>/
    # DELETE /projects/<id>/contacts/<id>/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="contacts/(?P<contact_pk>[^/.]+)",
    )
    def contacts_patch_delete_or_get(self, request, pk=None, contact_pk=None):
        if request.method == "GET":
            try:
                pc = ProjectContact.objects.select_related("contact", "project").get(
                    pk=contact_pk, project_id=pk
                )
            except ProjectContact.DoesNotExist:
                pc = None

            if not pc:
                return Response({"detail": "Not found."}, status=404)
            return Response(ProjectContactReadSerializer(pc).data)

        if request.method == "PATCH":
            return Response(
                {"detail": "Use /archive/ or /unarchive/ to change active state."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        if request.method == "DELETE":
            reason = request.data.get("reason", "")
            try:
                ProjectContactService.remove(contact_pk, reason)
            except ProjectContact.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)
            except Exception as e:
                return Response({"detail": str(e)}, status=400)
            return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH /projects/<id>/contacts/<id>/archive/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="contacts/(?P<contact_pk>[^/.]+)/archive",
    )
    def contact_archive(self, request, pk=None, contact_pk=None):
        ser = ProjectContactArchiveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            pc = ProjectContactService.archive(
                contact_pk, ser.validated_data.get("reason", "")
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ProjectContactReadSerializer(pc).data)

    # PATCH /projects/<id>/contacts/<id>/unarchive/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="contacts/(?P<contact_pk>[^/.]+)/unarchive",
    )
    def contact_unarchive(self, request, pk=None, contact_pk=None):
        try:
            pc = ProjectContactService.unarchive(contact_pk)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ProjectContactReadSerializer(pc).data)

    # GET /projects/<id>/contacts/history/
    @action(detail=True, methods=["get"], url_path="contacts/history")
    def contacts_history(self, request, pk=None):
        history = ProjectContactService.history(pk)
        return Response(ProjectContactHistorySerializer(history, many=True).data)

    # GET /projects/<id>/contacts/stats/
    @action(detail=True, methods=["get"], url_path="contacts/stats")
    def contacts_stats(self, request, pk=None):
        project_count = ProjectContact.objects.filter(
            project_id=pk,
            role=ProjectContact.ROLE_PROJECT,
            is_active=True,
        ).count()
        finance_count = ProjectContact.objects.filter(
            project_id=pk,
            role=ProjectContact.ROLE_FINANCE,
            is_active=True,
        ).count()
        return Response(
            {
                "project_count": project_count,
                "finance_count": finance_count,
                "max_per_role": 10,
            }
        )

    # GET /projects/<id>/links/
    # POST /projects/<id>/links/
    @action(detail=True, methods=["get", "post"], url_path="links")
    def links_create_or_get(self, request, pk=None):
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
                result = ProjectLinkService.list_links(
                    instance.pk,
                    request.query_params.get("search") or None,
                    page,
                    page_size,
                )
                serializer = ProjectLinkSerializer(result["results"], many=True)
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
                serializer = ProjectLinkWriteSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                print(serializer.validated_data)
                link = ProjectLinkService.create_link(
                    instance.pk,
                    title=serializer.validated_data["title"],
                    url=serializer.validated_data["url"],
                )
                return Response(
                    ProjectLinkSerializer(link).data,
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
            logger.exception("DatabaseError in links_create_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in links_create_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/links/<id>/
    # PATCH /projects/<id>/links/<id>/
    # DELETE /projects/<id>/links/<id>/
    @action(
        detail=True,
        methods=["get", "patch", "delete"],
        url_path="links/(?P<link_pk>[^/.]+)",
    )
    def links_patch_delete_or_get(self, request, pk=None, link_pk=None):
        try:
            try:
                instance = ProjectService.get_project(pk)
            except Project.DoesNotExist:
                logger.warning("Project %s does not exist.", pk)
                return Response(
                    {"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND
                )

            if request.method == "GET":
                link = ProjectLinkService.get_link(pk, link_pk)
                return Response(
                    ProjectLinkSerializer(link).data, status=status.HTTP_200_OK
                )

            if request.method == "PATCH":
                try:
                    link = ProjectLinkService.get_link(pk, link_pk)
                except ProjectLink.DoesNotExist:
                    logger.warning("Project link %s does not exist.", pk)
                    return Response(
                        {"error": "Project link not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                serializer = ProjectLinkWriteSerializer(
                    link, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)

                link = ProjectLinkService.update_link(
                    link,
                    title=serializer.validated_data.get("title"),
                    url=serializer.validated_data.get("url"),
                )
                return Response(ProjectLinkSerializer(link).data)

            if request.method == "DELETE":
                try:
                    link = ProjectLinkService.get_link(pk, link_pk)
                except ProjectLink.DoesNotExist:
                    logger.warning("Project link %s does not exist.", pk)
                    return Response(
                        {"error": "Project link not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                ProjectLinkService.delete_link(link)
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
            logger.exception("DatabaseError in links_patch_delete_or_get: %s", e)
            return Response(
                {"error": "A database error occurred."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in links_patch_delete_or_get: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /projects/<id>/attachments/
    # POST /projects/<id>/attachments/
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser],
    )
    def attachments_list_or_create(self, request, pk=None):
        try:
            try:
                ProjectService.get_project(pk)
            except Project.DoesNotExist:
                return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

            if request.method == "GET":
                attachments = ProjectAttachmentService.list_attachments(pk)
                return Response(ProjectAttachmentSerializer(attachments, many=True).data)

            file_obj = request.FILES.get("file")
            if not file_obj:
                return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

            uploaded_by = request.user.get_full_name() or request.user.email if request.user.is_authenticated else ""
            att = ProjectAttachmentService.save_attachment(pk, file_obj, uploaded_by=uploaded_by)
            return Response(ProjectAttachmentSerializer(att).data, status=status.HTTP_201_CREATED)

        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DatabaseError in attachments_list_or_create: %s", e)
            return Response({"error": "A database error occurred."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in attachments_list_or_create: %s", e)
            return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # DELETE /projects/<id>/attachments/<att_id>/
    # GET    /projects/<id>/attachments/<att_id>/download/
    @action(
        detail=True,
        methods=["delete", "get"],
        url_path="attachments/(?P<att_pk>[^/.]+)",
        parser_classes=[MultiPartParser, FormParser],
    )
    def attachments_delete_or_download(self, request, pk=None, att_pk=None):
        try:
            try:
                ProjectService.get_project(pk)
            except Project.DoesNotExist:
                return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

            try:
                att = ProjectAttachmentService.get_attachment(pk, att_pk)
            except ProjectAttachment.DoesNotExist:
                return Response({"error": "Attachment not found."}, status=status.HTTP_404_NOT_FOUND)

            if request.method == "DELETE":
                ProjectAttachmentService.delete_attachment(att)
                return Response(status=status.HTTP_204_NO_CONTENT)

            # GET — download
            file_bytes, content_type = ProjectAttachmentService.get_file_bytes(att)
            resp = HttpResponse(file_bytes, content_type=content_type or "application/octet-stream")
            resp["Content-Disposition"] = f'attachment; filename="{att.file_name}"'
            return resp

        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DatabaseError in attachments_delete_or_download: %s", e)
            return Response({"error": "A database error occurred."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in attachments_delete_or_download: %s", e)
            return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectViewViewSet(viewsets.ViewSet):
    # GET /project-views/
    def list(self, request):
        try:
            views = ProjectViewService.list_all()
            serializer = ProjectViewSerializer(views, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
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

    # POST /project-views/
    def create(self, request):
        try:
            data = request.data
            view = ProjectViewService.create(
                name=data.get("name", ""),
                filters=data.get("filters", {}),
                columns=data.get("columns", []),
                ordering=data.get("ordering", "-created_at"),
                is_default=data.get("is_default", False),
            )

            serializer = ProjectViewSerializer(view)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
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

    # GET /project-views/<id>/
    def retrieve(self, request, pk=None):
        try:
            view = ProjectViewService.get(pk=pk)
            return Response(ProjectViewSerializer(view).data, status=status.HTTP_200_OK)
        except ProjectView.DoesNotExist:
            return Response(
                {"error": "Project view not found."}, status=status.HTTP_404_NOT_FOUND
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

    # PATCH /project-views/<id>/
    def partial_update(self, request, pk=None):
        try:
            try:
                view = ProjectViewService.get(pk=pk)
            except ProjectView.DoesNotExist:
                return Response(
                    {"error": "Project view not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            allowed = {"name", "filters", "columns", "ordering", "is_default"}
            kwargs = {k: v for k, v in request.data.items() if k in allowed}
            view = ProjectViewService.update(pk, **kwargs)
            return Response(ProjectViewSerializer(view).data, status=status.HTTP_200_OK)
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

    # DELETE /project-views/<id>/
    def destroy(self, request, pk=None):
        try:
            ProjectViewService.delete(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectView.DoesNotExist:
            return Response(
                {"error": "Project view not found."}, status=status.HTTP_404_NOT_FOUND
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
