import base64
import logging

from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import (
    ResourcePlan,
    ResourcePlanVersion,
    ResourcePlanScope,
    ResourcePlanComment,
    ResourcePlanVersionProject,
    ResourcePlanVersionProjectTeam,
    ResourcePlanVersionProjectBudgetRelease,
    PlanPhase,
    PlanPhaseSegment,
    PlanPhaseDependency,
    PlanPhasePause,
    PlanAssignment,
    PlanEngineJob,
    Conflict,
    ManpowerRequest,
    PlaceholderEngineer,
    PlaceholderEngineerAbsence,
)
from .serializers import (
    ResourcePlanSerializer,
    ResourcePlanListSerializer,
    ResourcePlanVersionSerializer,
    ResourcePlanScopeSerializer,
    ResourcePlanCommentSerializer,
    ResourcePlanCreateSerializer,
    ResourcePlanVersionProjectSerializer,
    ResourcePlanVersionProjectTeamSerializer,
    ResourcePlanVersionProjectBudgetReleaseSerializer,
    PlanPhaseSerializer,
    PlanPhaseSegmentSerializer,
    PlanPhaseDependencySerializer,
    PlanPhasePauseSerializer,
    PlanAssignmentSerializer,
    PlanEngineJobSerializer,
    PlanEngineJobStatusSerializer,
    PlaceholderLeaveSerializer,
    ResourcePlanAllocationSetSerializer,
    ConflictSerializer,
    ManpowerRequestSerializer,
    PlaceholderEngineerSerializer,
    PlaceholderEngineerAbsenceSerializer,
)
from .services import (
    ResourcePlanService,
    ResourcePlanVersionService,
    ResourcePlanScopeService,
    ResourcePlanCommentService,
    ResourcePlanVersionConfigService,
    PlanPhaseService,
    PlanAssignmentService,
    PlanEngineJobService,
    PlaceholderLeaveService,
    CapacityService,
    CapacitySnapshotService,
    AllocationSetService,
    CellUpdateService,
    CellCreateService,
    ConflictService,
    ConflictResolutionService,
    ManpowerRequestService,
    PlaceholderEngineerService,
    PlaceholderEngineerAbsenceService,
    TeamUtilisationService,
    MemberUtilisationService,
    ProgrammeRollupService,
    SnapshotService,
)

logger = logging.getLogger(__name__)


class ResourcePlanViewSet(viewsets.ViewSet):
    # GET /resource-plans/
    def list(self, request):
        search = request.query_params.get("search", "").strip()
        plan_type = request.query_params.get("plan_type", "")
        status_filter = request.query_params.get("status", "")
        fy_id = request.query_params.get("financial_year", "")
        order_by = request.query_params.get("order_by", "-created_at")

        is_active_str = request.query_params.get("is_active", "")
        if is_active_str.lower() == "true":
            is_active = True
        elif is_active_str.lower() == "false":
            is_active = False
        else:
            is_active = None

        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ResourcePlanService.list_plans(
                search=search or None,
                plan_type=plan_type or None,
                version_status=status_filter or None,
                fy_id=int(fy_id) if fy_id and fy_id.isdigit() else None,
                is_active=is_active,
                order_by=order_by,
                page=page,
                page_size=page_size,
            )
            serializer = ResourcePlanListSerializer(result["results"], many=True)
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

    # POST /resource-plans/
    def create(self, request):
        serializer = ResourcePlanCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cd = serializer.validated_data
        try:
            plan = ResourcePlanService.create_plan(
                name=cd["name"],
                description=cd.get("description") or None,
                plan_type=cd["plan_type"],
                financial_year_id=cd["financial_year"],
                project_id=cd.get("project"),
                programme_id=cd.get("programme"),
                team_id=cd.get("team"),
            )
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            return Response(
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": str(exc)}
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # GET /resource-plans/<id>/
    def retrieve(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # PATCH /resource-plans/<id>/
    def partial_update(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            plan = ResourcePlanService.update_plan(
                plan,
                name=request.data.get("name"),
                description=request.data.get("description"),
                is_active=request.data.get("is_active"),
                threshold_pct=request.data.get("threshold_pct"),
            )
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except DjangoValidationError as exc:
            return Response(
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": str(exc)}
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # DELETE /resource-plans/<id>/
    def destroy(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            ResourcePlanService.delete_plan(plan)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # GET /resource-plans/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def statistics(self, request):
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = ResourcePlanService.list_stats(fields=fields)
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

    # POST /resource-plans/<id>/activate/
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            plan = ResourcePlanService.activate_plan(plan)
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/<id>/lock/
    @action(detail=True, methods=["post"], url_path="lock")
    def lock(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            plan = ResourcePlanService.lock_plan(plan)
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/<id>/archive/
    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            plan = ResourcePlanService.archive_plan(plan)
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/<id>/unarchive/
    @action(detail=True, methods=["post"], url_path="unarchive")
    def unarchive(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            plan = ResourcePlanService.unarchive_plan(plan)
            return Response(
                ResourcePlanSerializer(plan).data, status=status.HTTP_200_OK
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/<id>/clone/
    @action(detail=True, methods=["post"], url_path="clone")
    def clone(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        new_name = request.data.get("name", "").strip()
        if not new_name:
            return Response(
                {"name": "Name is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        include_config = str(request.data.get("include_config", "false")).lower() == "true"
        try:
            new_plan = ResourcePlanService.clone_plan(plan, new_name, include_config=include_config)
            return Response(
                ResourcePlanSerializer(new_plan).data, status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            return Response(
                (
                    exc.message_dict
                    if hasattr(exc, "message_dict")
                    else {"detail": str(exc)}
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

    # POST /resource-plans/<id>/new-version/
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        threshold_pct = request.data.get("threshold_pct")
        try:
            new_plan = ResourcePlanService.new_version(plan, threshold_pct=threshold_pct)
            return Response(
                ResourcePlanSerializer(new_plan).data, status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Unexpected error in new_version: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/<id>/restore/<id>/
    @action(detail=True, methods=["post"], url_path=r"restore/(?P<source_pk>\d+)")
    def restore(self, request, pk=None, source_pk=None):
        try:
            ResourcePlanService.get_plan(pk)  # Validate plan exists
            source_plan = ResourcePlanService.get_plan(plan_id=source_pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        include_config = str(request.data.get("include_config", "false")).lower() == "true"
        try:
            new_plan = ResourcePlanService.restore_version(source_plan, include_config=include_config)
            return Response(
                ResourcePlanSerializer(new_plan).data, status=status.HTTP_201_CREATED
            )
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Unexpected error in restore: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # GET /resource-plans/<id>/versions/
    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            plan = ResourcePlanService.get_plan(pk)
            result = ResourcePlanService.get_versions(plan, page, page_size)
            serializer = ResourcePlanVersionSerializer(result["results"], many=True)
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
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    # GET /resource-plans/options/
    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        opts = ResourcePlanScopeService.get_options()
        return Response(opts, status=status.HTTP_200_OK)

    # GET /resource-plans/<id>/comments/
    # POST /resource-plans/<id>/comments/
    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20

            result = ResourcePlanCommentService.list_comments(plan, page, page_size)
            serializer = ResourcePlanCommentSerializer(result["results"], many=True)
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
            comment_text = request.data.get("comment", "")
            posted_by = request.user.get_full_name() or request.user.email
            try:
                mentioned_ids = request.data.get("mentioned_user_ids") or []
                comment = ResourcePlanCommentService.add_comment(
                    plan, comment_text, posted_by, user=request.user, mentioned_user_ids=mentioned_ids
                )
                return Response(
                    ResourcePlanCommentSerializer(comment).data,
                    status=status.HTTP_201_CREATED,
                )
            except DjangoValidationError as exc:
                return Response(
                    (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else {"detail": str(exc)}
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

    # POST /resource-plans/<id>/comments/upload-image/
    @action(
        detail=True, methods=["post"],
        url_path="comments/upload-image",
        parser_classes=[MultiPartParser, FormParser],
    )
    def comments_upload_image(self, request, pk=None):
        try:
            ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get("image")
        if not file_obj:
            return Response({"error": "No image uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        if file_obj.size > 10 * 1024 * 1024:
            return Response({"error": "Image exceeds 10 MB limit."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = getattr(file_obj, "content_type", "image/png") or "image/png"
        raw = file_obj.read()
        b64 = base64.b64encode(raw).decode("ascii")
        data_uri = f"data:{content_type};base64,{b64}"
        return Response({"url": data_uri}, status=status.HTTP_201_CREATED)

    # GET /resource-plans/check-name/
    @action(detail=False, methods=["get"], url_path="check-name")
    def check_name(self, request):
        name = request.query_params.get("name", "").strip()
        exclude_id = request.query_params.get("exclude_id")
        if not name:
            return Response({"unique": False, "message": "Name is required."})

        is_unique = ResourcePlanService.check_name_unique(
            name, exclude_pk=exclude_id or None
        )
        return Response({"unique": is_unique}, status=status.HTTP_200_OK)

    # POST /resource-plans/<id>/engine/run/
    @action(detail=True, methods=["post"], url_path="engine/run")
    def engine_run(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

        # Resolve the version to run against (latest DRAFT, or explicit version_id)
        version_id = request.data.get("version_id")
        if version_id:
            try:
                version = ResourcePlanVersion.objects.get(pk=version_id, plan=plan)
            except ResourcePlanVersion.DoesNotExist:
                return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            version = ResourcePlanVersion.objects.filter(plan=plan).order_by("-version").first()
            if not version:
                return Response({"detail": "Plan has no versions."}, status=status.HTTP_400_BAD_REQUEST)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        mode = request.data.get("mode", PlanEngineJob.MODE_VALIDATE)
        if mode not in (PlanEngineJob.MODE_VALIDATE, PlanEngineJob.MODE_FULL):
            return Response({"detail": "Invalid mode."}, status=status.HTTP_400_BAD_REQUEST)

        include_current = bool(request.data.get("include_current_sprint", False))
        dry_run = bool(request.data.get("dry_run", False))
        remove_overrides = bool(request.data.get("remove_overrides", False))

        try:
            job = PlanEngineJobService.create_job(
                plan=plan,
                version=version,
                mode=mode,
                include_current_sprint=include_current,
                dry_run=dry_run,
                remove_overrides=remove_overrides,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)}
            running_id = detail.get("running_job_id") or detail.get("running_job_id")
            return Response(
                {"detail": detail.get("detail", "A job is already running."), "running_job_id": running_id},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"job_id": job.pk}, status=status.HTTP_201_CREATED)

    # GET /resource-plans/<id>/engine/jobs/
    @action(detail=True, methods=["get"], url_path="engine/jobs")
    def engine_jobs(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)
        mode_filter = request.query_params.get("mode") or None
        version_id_filter = request.query_params.get("version_id") or None
        jobs = PlanEngineJobService.list_jobs(plan, mode_filter, version_id=version_id_filter)
        page = request.query_params.get("page", 1)
        page_size = 20
        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1
        total = jobs.count()
        start = (page - 1) * page_size
        jobs_page = jobs[start: start + page_size]
        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "num_pages": max(1, -(-total // page_size)),
            "results": PlanEngineJobSerializer(jobs_page, many=True).data,
        })

    # GET /resource-plans/<id>/engine/jobs/<job_id>/
    @action(detail=True, methods=["get"], url_path=r"engine/jobs/(?P<job_pk>\d+)")
    def engine_job_detail(self, request, pk=None, job_pk=None):
        try:
            ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            job = PlanEngineJobService.get_job(job_pk)
        except PlanEngineJob.DoesNotExist:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlanEngineJobSerializer(job).data)

    # GET /resource-plans/<id>/engine/jobs/<job_id>/status/
    @action(detail=True, methods=["get"], url_path=r"engine/jobs/(?P<job_pk>\d+)/status")
    def engine_job_status(self, request, pk=None, job_pk=None):
        try:
            ResourcePlanService.get_plan(pk)
        except ResourcePlan.DoesNotExist:
            return Response({"detail": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            job = PlanEngineJobService.get_job(job_pk)
        except PlanEngineJob.DoesNotExist:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlanEngineJobStatusSerializer(job).data)


def _version_not_found():
    return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)


def _entry_not_found():
    return Response({"detail": "Project entry not found."}, status=status.HTTP_404_NOT_FOUND)


def _validation_error_response(exc):
    return Response(
        exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class ResourcePlanVersionConfigViewSet(viewsets.ViewSet):
    """Nested resources under a ResourcePlanVersion."""

    def _get_version(self, pk):
        return ResourcePlanVersionConfigService.get_version(pk)

    # GET /resource-plans/{plan_pk}/versions/{pk}/
    def retrieve(self, request, pk=None, **kwargs):
        try:
            version = self._get_version(pk)
            return Response(ResourcePlanVersionSerializer(version).data)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()

    # PATCH /resource-plans/{plan_pk}/versions/{pk}/
    def partial_update(self, request, pk=None, **kwargs):
        return Response(
            {"detail": "Sprint point price is now managed via Configurations (SPRINT_POINT_PRICE)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # GET /resource-plans/{plan_pk}/versions/{pk}/projects/
    # POST /resource-plans/{plan_pk}/versions/{pk}/projects/
    @action(detail=True, methods=["get", "post"], url_path="projects")
    def projects(self, request, pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()

        if request.method == "GET":
            try:
                page = int(request.query_params.get("page", 1))
                page_size = min(int(request.query_params.get("page_size", 20)), 100)
            except (ValueError, TypeError):
                page, page_size = 1, 20
            search = request.query_params.get("search", "").strip() or None
            programme_id = request.query_params.get("programme", "")
            result = ResourcePlanVersionConfigService.list_projects(
                version, page, page_size, search,
                programme_id=int(programme_id) if programme_id and programme_id.isdigit() else None,
            )
            serializer = ResourcePlanVersionProjectSerializer(result["results"], many=True)
            return Response({
                "results": serializer.data,
                "pagination": {
                    "total_count": result["total_count"],
                    "total_pages": result["total_pages"],
                    "current_page": result["current_page"],
                    "page_size": result["page_size"],
                    "has_next": result["has_next"],
                    "has_previous": result["has_previous"],
                },
            })

        # POST
        lock = _snapshot_locked(version)
        if lock:
            return lock
        project_id = request.data.get("project")
        basis = request.data.get("basis", "").strip()
        basis_amount = request.data.get("basis_amount")
        priority_override = request.data.get("priority_override")
        confidence_override = request.data.get("confidence_override")

        if not project_id or not basis:
            return Response({"detail": "project and basis are required."}, status=status.HTTP_400_BAD_REQUEST)

        estimate_id_raw = request.data.get("estimate_id")
        try:
            entry = ResourcePlanVersionConfigService.add_project(
                version, project_id, basis,
                basis_amount=basis_amount,
                priority_override=priority_override,
                confidence_override=confidence_override,
                estimate_id=int(estimate_id_raw) if estimate_id_raw and str(estimate_id_raw).isdigit() else None,
            )
            return Response(
                ResourcePlanVersionProjectSerializer(entry).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET /resource-plans/{plan_pk}/versions/{pk}/projects/unmapped/
    @action(detail=True, methods=["get"], url_path="projects/unmapped")
    def projects_unmapped(self, request, pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        search = request.query_params.get("search", "").strip() or None
        return Response(ResourcePlanVersionConfigService.get_unmapped_projects(version, search))

    # GET /resource-plans/{plan_pk}/versions/{pk}/projects/options/
    @action(detail=True, methods=["get"], url_path="projects/options")
    def projects_options(self, request, pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        return Response(ResourcePlanVersionConfigService.get_options(version))

    # GET/PATCH/DELETE /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/
    @action(detail=True, methods=["get", "patch", "delete"],
            url_path=r"projects/(?P<entry_pk>\d+)")
    def project_detail(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()

        if request.method == "GET":
            return Response(ResourcePlanVersionProjectSerializer(entry).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            ResourcePlanVersionConfigService.delete_project_entry(entry)
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PATCH
        estimate_id_raw = request.data.get("estimate_id")
        try:
            entry = ResourcePlanVersionConfigService.update_project_entry(
                entry,
                basis=request.data.get("basis"),
                basis_amount=request.data.get("basis_amount"),
                priority_override=request.data.get("priority_override"),
                confidence_override=request.data.get("confidence_override"),
                start_sprint_id=request.data.get("start_sprint"),
                end_sprint_id=request.data.get("end_sprint"),
                dates_strict=request.data.get("dates_strict"),
                budget_release_mode=request.data.get("budget_release_mode"),
                estimate_id=int(estimate_id_raw) if estimate_id_raw and str(estimate_id_raw).isdigit() else None,
            )
            return Response(ResourcePlanVersionProjectSerializer(entry).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # POST /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/resync/
    @action(detail=True, methods=["post"], url_path=r"projects/(?P<entry_pk>\d+)/resync")
    def project_resync(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()

        if entry.basis == ResourcePlanVersionProject.BASIS_CUSTOM:
            return Response({"detail": "Resync not applicable for CUSTOM basis."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            entry = ResourcePlanVersionConfigService.resync_project(entry)
            return Response(ResourcePlanVersionProjectSerializer(entry).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # PATCH /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/reorder/
    @action(detail=True, methods=["patch"], url_path=r"projects/(?P<entry_pk>\d+)/reorder")
    def project_reorder(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()
        try:
            entry = ResourcePlanVersionConfigService.reorder_project(entry, request.data.get("display_order"))
            return Response({"id": entry.id, "display_order": entry.display_order})
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET/POST /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/teams/
    @action(detail=True, methods=["get", "post"],
            url_path=r"projects/(?P<entry_pk>\d+)/teams")
    def teams(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()

        if request.method == "GET":
            teams = ResourcePlanVersionConfigService.list_teams(entry)
            return Response(ResourcePlanVersionProjectTeamSerializer(teams, many=True).data)

        # POST
        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            team_entry = ResourcePlanVersionConfigService.add_team(
                entry,
                team_id=request.data.get("team"),
                allocation_type=request.data.get("allocation_type"),
                value=request.data.get("value"),
                sequence_order=request.data.get("sequence_order", 1),
            )
            return Response(
                ResourcePlanVersionProjectTeamSerializer(team_entry).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid value."}, status=status.HTTP_400_BAD_REQUEST)

    # GET /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/teams/options/
    @action(detail=True, methods=["get"],
            url_path=r"projects/(?P<entry_pk>\d+)/teams/options")
    def teams_options(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()
        return Response(ResourcePlanVersionConfigService.get_team_options(entry))

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/teams/{team_entry_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"projects/(?P<entry_pk>\d+)/teams/(?P<team_entry_pk>\d+)")
    def team_detail(self, request, pk=None, entry_pk=None, team_entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()
        try:
            team_entry = entry.teams.get(pk=team_entry_pk)
        except ResourcePlanVersionProjectTeam.DoesNotExist:
            return Response({"detail": "Team entry not found."}, status=status.HTTP_404_NOT_FOUND)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            ResourcePlanVersionConfigService.delete_team(team_entry)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            team_entry = ResourcePlanVersionConfigService.update_team(
                team_entry,
                allocation_type=request.data.get("allocation_type"),
                value=request.data.get("value"),
                sequence_order=request.data.get("sequence_order"),
            )
            return Response(ResourcePlanVersionProjectTeamSerializer(team_entry).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET/POST /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/budget-releases/
    @action(detail=True, methods=["get", "post"],
            url_path=r"projects/(?P<entry_pk>\d+)/budget-releases")
    def budget_releases(self, request, pk=None, entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()

        if request.method == "GET":
            releases = ResourcePlanVersionConfigService.list_budget_releases(entry)
            return Response(ResourcePlanVersionProjectBudgetReleaseSerializer(releases, many=True).data)

        try:
            release = ResourcePlanVersionConfigService.add_budget_release(
                entry,
                entry_type=request.data.get("entry_type"),
                amount=request.data.get("amount"),
                sprint_id=request.data.get("sprint"),
                month=request.data.get("month"),
                notes=request.data.get("notes"),
            )
            return Response(
                ResourcePlanVersionProjectBudgetReleaseSerializer(release).data,
                status=status.HTTP_201_CREATED,
            )
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{pk}/projects/{entry_pk}/budget-releases/{release_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"projects/(?P<entry_pk>\d+)/budget-releases/(?P<release_pk>\d+)")
    def budget_release_detail(self, request, pk=None, entry_pk=None, release_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()
        try:
            release = entry.budget_releases.get(pk=release_pk)
        except ResourcePlanVersionProjectBudgetRelease.DoesNotExist:
            return Response({"detail": "Budget release not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            ResourcePlanVersionConfigService.delete_budget_release(release)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            release = ResourcePlanVersionConfigService.update_budget_release(
                release,
                amount=request.data.get("amount"),
                notes=request.data.get("notes"),
            )
            return Response(ResourcePlanVersionProjectBudgetReleaseSerializer(release).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)


def _phase_not_found():
    return Response({"detail": "Phase not found."}, status=status.HTTP_404_NOT_FOUND)


def _team_entry_not_found():
    return Response({"detail": "Team entry not found."}, status=status.HTTP_404_NOT_FOUND)


def _snapshot_locked(version):
    """Return 423 Response if a snapshot job is in progress for this version, else None."""
    from .models import ResourcePlanSnapshot
    snap = ResourcePlanSnapshot.objects.filter(
        version=version,
        status__in=[ResourcePlanSnapshot.STATUS_PENDING, ResourcePlanSnapshot.STATUS_IN_PROGRESS],
    ).first()
    if snap:
        return Response(
            {'detail': 'A snapshot is in progress. All write operations are locked.',
             'snapshot_id': snap.pk},
            status=423,
        )
    return None


class AllocationGridViewSet(viewsets.ViewSet):
    """Grid endpoints for capacity and absence data, nested under a version."""

    def _get_version(self, plan_pk, version_pk):
        from .models import ResourcePlanVersion
        try:
            return ResourcePlanVersion.objects.select_related("plan").get(
                pk=version_pk, plan__pk=plan_pk
            )
        except ResourcePlanVersion.DoesNotExist:
            return None

    def grid_teams(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CapacityService.get_team_tabs(version))

    def grid_capacity(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        team_id = request.query_params.get("team") or None
        if team_id:
            try:
                team_id = int(team_id)
            except (ValueError, TypeError):
                team_id = None
        return Response(CapacityService.get_capacity_grid(version, team_id))

    def grid_absences(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        team_id = request.query_params.get("team") or None
        if team_id:
            try:
                team_id = int(team_id)
            except (ValueError, TypeError):
                team_id = None
        return Response(CapacityService.get_absences_grid(version, team_id))

    def placeholder_leaves(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        member_id = request.query_params.get("team_member") or None
        team_id = request.query_params.get("team") or None
        try:
            member_id = int(member_id) if member_id else None
        except (ValueError, TypeError):
            member_id = None
        try:
            team_id = int(team_id) if team_id else None
        except (ValueError, TypeError):
            team_id = None
        qs = PlaceholderLeaveService.list_for_version(version, member_id, team_id)
        page_param = request.query_params.get("page", None)
        if page_param is not None:
            page_size = 20
            try:
                page = max(1, int(page_param))
            except (ValueError, TypeError):
                page = 1
            total = qs.count()
            start = (page - 1) * page_size
            return Response({
                "count": total,
                "page": page,
                "page_size": page_size,
                "num_pages": max(1, -(-total // page_size)),
                "results": PlaceholderLeaveSerializer(qs[start: start + page_size], many=True).data,
            })
        return Response(PlaceholderLeaveSerializer(qs, many=True).data)

    def placeholder_leave_detail(self, request, plan_pk, pk, pl_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        if request.method in ('PATCH', 'DELETE'):
            lock = _snapshot_locked(version)
            if lock:
                return lock
        try:
            from .models import PlaceholderLeave
            pl = PlaceholderLeave.objects.get(pk=pl_pk, version=version)
        except PlaceholderLeave.DoesNotExist:
            return Response({"detail": "Placeholder leave not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "PATCH":
            days = request.data.get("days")
            notes = request.data.get("notes")
            if days is None:
                return Response({"days": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                updated = PlaceholderLeaveService.update_placeholder(pl, days, notes)
                CapacitySnapshotService.sync_record(version, pl.team_member_id, pl.sprint_id)
                ResourcePlanVersion.objects.filter(pk=version.pk).update(has_pl_overrides=True)
                return Response(PlaceholderLeaveSerializer(updated).data)
            except Exception as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == "DELETE":
            member_id, sprint_id = pl.team_member_id, pl.sprint_id
            PlaceholderLeaveService.delete_placeholder(pl)
            CapacitySnapshotService.sync_record(version, member_id, sprint_id)
            ResourcePlanVersion.objects.filter(pk=version.pk).update(has_pl_overrides=True)
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # ── Allocation sets ───────────────────────────────────────────────────────

    def allocation_sets(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        sets = AllocationSetService.list_sets(version)
        return Response(ResourcePlanAllocationSetSerializer(sets, many=True).data)

    def allocation_set_detail(self, request, plan_pk, pk, set_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        alloc_set = AllocationSetService.get_set(version, set_pk)
        if not alloc_set:
            return Response({"detail": "Allocation set not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "PATCH":
            notes = request.data.get("notes")
            updated = AllocationSetService.update_notes(alloc_set, notes)
            return Response(ResourcePlanAllocationSetSerializer(updated).data)

        return Response(ResourcePlanAllocationSetSerializer(alloc_set).data)

    def allocation_set_activate(self, request, plan_pk, pk, set_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        lock = _snapshot_locked(version)
        if lock:
            return lock
        alloc_set = AllocationSetService.get_set(version, set_pk)
        if not alloc_set:
            return Response({"detail": "Allocation set not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            activated = AllocationSetService.activate(alloc_set)
            return Response(ResourcePlanAllocationSetSerializer(activated).data)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    # ── Allocation grid endpoints (Tables 3 & 4) ──────────────────────────────

    def grid_allocations(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        def _int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None

        allocation_set_id = _int(request.query_params.get("allocation_set"))
        team_id = _int(request.query_params.get("team"))
        return Response(AllocationSetService.get_allocations_grid(version, allocation_set_id, team_id))

    def grid_allocated_capacity(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        def _int(val):
            try:
                return int(val) if val else None
            except (ValueError, TypeError):
                return None

        allocation_set_id = _int(request.query_params.get("allocation_set"))
        team_id = _int(request.query_params.get("team"))
        return Response(AllocationSetService.get_allocated_capacity_grid(version, allocation_set_id, team_id))

    def grid_cell_update(self, request, plan_pk, pk, alloc_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        lock = _snapshot_locked(version)
        if lock:
            return lock

        days = request.data.get("days")
        if days is None:
            return Response({"days": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = CellUpdateService.update_cell(version, alloc_pk, days)
            return Response(result, status=status.HTTP_200_OK)
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def grid_cell_create(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        lock = _snapshot_locked(version)
        if lock:
            return lock

        try:
            result = CellCreateService.create_cell(version, request.data)
            return Response(result, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, "message_dict") else {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # ── Conflict endpoints ────────────────────────────────────────────────────

    def conflict_summary(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        alloc_set_id = request.query_params.get('allocation_set')
        try:
            alloc_set_id = int(alloc_set_id) if alloc_set_id else None
        except (ValueError, TypeError):
            alloc_set_id = None
        summary = ConflictService.get_summary(version, alloc_set_id)
        return Response(summary)

    def conflict_list(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        def _int(v): return int(v) if v else None
        try:
            qs = ConflictService.list_conflicts(
                version,
                allocation_set_id=_int(request.query_params.get('allocation_set')),
                severity=request.query_params.get('severity'),
                status=request.query_params.get('status'),
                conflict_type=request.query_params.get('conflict_type'),
            )
            return Response(ConflictSerializer(qs, many=True).data)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def conflict_detail(self, request, plan_pk, pk, conflict_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        conflict = ConflictService.get_conflict(version, conflict_pk)
        if not conflict:
            return Response({"detail": "Conflict not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ConflictSerializer(conflict).data)

    def conflict_resolve(self, request, plan_pk, pk, conflict_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        conflict = ConflictService.get_conflict(version, conflict_pk)
        if not conflict:
            return Response({"detail": "Conflict not found."}, status=status.HTTP_404_NOT_FOUND)
        resolution_type = request.data.get('resolution_type')
        notes = request.data.get('notes', '')
        extra_data = request.data.get('extra_data', {})
        if not resolution_type:
            return Response({"resolution_type": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            updated = ConflictResolutionService.resolve(conflict, resolution_type, notes, extra_data)
            return Response(ConflictSerializer(updated).data)
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # ── Manpower request endpoints ────────────────────────────────────────────

    def manpower_list(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        def _int(v): return int(v) if v else None
        qs = ConflictService.list_manpower_requests(
            version,
            allocation_set_id=_int(request.query_params.get('allocation_set')),
            status=request.query_params.get('status'),
        )
        return Response(ManpowerRequestSerializer(qs, many=True).data)

    def manpower_detail(self, request, plan_pk, pk, mp_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        mp = ConflictService.get_manpower_request(version, mp_pk)
        if not mp:
            return Response({"detail": "Manpower request not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ManpowerRequestSerializer(mp).data)

    def manpower_hire(self, request, plan_pk, pk, mp_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        mp = ConflictService.get_manpower_request(version, mp_pk)
        if not mp:
            return Response({"detail": "Manpower request not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ManpowerRequestService.hire(
                mp,
                onboard_sprint_id=request.data.get('onboard_sprint'),
                notes=request.data.get('notes'),
            )
            return Response(ManpowerRequestSerializer(mp).data)
        except DjangoValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def manpower_rebalance(self, request, plan_pk, pk, mp_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        mp = ConflictService.get_manpower_request(version, mp_pk)
        if not mp:
            return Response({"detail": "Manpower request not found."}, status=status.HTTP_404_NOT_FOUND)
        ManpowerRequestService.rebalance(mp, notes=request.data.get('notes'))
        return Response(ManpowerRequestSerializer(mp).data)

    def manpower_dismiss(self, request, plan_pk, pk, mp_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        mp = ConflictService.get_manpower_request(version, mp_pk)
        if not mp:
            return Response({"detail": "Manpower request not found."}, status=status.HTTP_404_NOT_FOUND)
        ManpowerRequestService.dismiss(mp, notes=request.data.get('notes'))
        return Response(ManpowerRequestSerializer(mp).data)

    # ── Placeholder engineers (Phase 10) ─────────────────────────────────────

    def placeholder_engineer_list(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        qs = PlaceholderEngineer.objects.filter(version=version).select_related(
            'team', 'manpower_request', 'onboard_sprint', 'engine_suggested_sprint', 'replaced_by'
        )
        return Response(PlaceholderEngineerSerializer(qs, many=True).data)

    def placeholder_engineer_detail(self, request, plan_pk, pk, ph_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ph = PlaceholderEngineer.objects.select_related(
                'team', 'manpower_request', 'onboard_sprint', 'engine_suggested_sprint', 'replaced_by'
            ).get(pk=ph_pk, version=version)
        except PlaceholderEngineer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlaceholderEngineerSerializer(ph).data)

    def placeholder_engineer_update(self, request, plan_pk, pk, ph_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ph = PlaceholderEngineer.objects.get(pk=ph_pk, version=version)
        except PlaceholderEngineer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        onboard_sprint_id = request.data.get('onboard_sprint')
        if onboard_sprint_id:
            try:
                ph = PlaceholderEngineerService.update_onboard_sprint(ph, onboard_sprint_id)
                return Response(PlaceholderEngineerSerializer(ph).data)
            except DjangoValidationError as exc:
                return Response(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PlaceholderEngineerSerializer(ph).data)

    def placeholder_engineer_replace(self, request, plan_pk, pk, ph_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            ph = PlaceholderEngineer.objects.get(pk=ph_pk, version=version)
        except PlaceholderEngineer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        team_member_id = request.data.get('team_member')
        if not team_member_id:
            return Response({'team_member': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ph = PlaceholderEngineerService.replace_with_hire(ph, team_member_id)
            return Response(PlaceholderEngineerSerializer(ph).data)
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def placeholder_engineer_absence_list(self, request, plan_pk, pk, ph_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ph = PlaceholderEngineer.objects.get(pk=ph_pk, version=version)
        except PlaceholderEngineer.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        absences = ph.absences.select_related('sprint').all()
        return Response(PlaceholderEngineerAbsenceSerializer(absences, many=True).data)

    def placeholder_engineer_absence_update(self, request, plan_pk, pk, ph_pk, absence_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)
        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            ph = PlaceholderEngineer.objects.get(pk=ph_pk, version=version)
            absence = PlaceholderEngineerAbsence.objects.get(pk=absence_pk, placeholder_engineer=ph)
        except (PlaceholderEngineer.DoesNotExist, PlaceholderEngineerAbsence.DoesNotExist):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        override_days = request.data.get('override_days')
        notes = request.data.get('override_notes', '')
        try:
            absence = PlaceholderEngineerAbsenceService.override_absence(absence, override_days, notes)
            return Response(PlaceholderEngineerAbsenceSerializer(absence).data)
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # ── Utilisation endpoints (Phase 11) ──────────────────────────────────────

    def utilisation_teams(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        def _int_list(val):
            if not val:
                return None
            try:
                return [int(x.strip()) for x in val.split(',') if x.strip()]
            except (ValueError, TypeError):
                return None

        allocation_set_id = request.query_params.get('allocation_set')
        try:
            allocation_set_id = int(allocation_set_id) if allocation_set_id else None
        except (ValueError, TypeError):
            allocation_set_id = None

        team_ids = _int_list(request.query_params.get('teams'))
        employment_type_ids = _int_list(request.query_params.get('employment_types'))
        show_auto = request.query_params.get('show_auto', '0') not in ('', '0', 'false', 'False')
        return Response(TeamUtilisationService.get_team_utilisation(version, allocation_set_id, team_ids, employment_type_ids, show_auto=show_auto))

    def utilisation_members(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        def _int_list(val):
            if not val:
                return None
            try:
                return [int(x.strip()) for x in val.split(',') if x.strip()]
            except (ValueError, TypeError):
                return None

        allocation_set_id = request.query_params.get('allocation_set')
        try:
            allocation_set_id = int(allocation_set_id) if allocation_set_id else None
        except (ValueError, TypeError):
            allocation_set_id = None

        show_auto = request.query_params.get('show_auto', '0') not in ('', '0', 'false', 'False')
        return Response(MemberUtilisationService.get_member_utilisation(
            version,
            allocation_set_id=allocation_set_id,
            team_ids=_int_list(request.query_params.get('teams')),
            member_ids=_int_list(request.query_params.get('members')),
            employment_type_ids=_int_list(request.query_params.get('employment_types')),
            project_ids=_int_list(request.query_params.get('projects')),
            show_auto=show_auto,
        ))

    def utilisation_programmes(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        def _int_list(val):
            if not val:
                return None
            try:
                return [int(x.strip()) for x in val.split(',') if x.strip()]
            except (ValueError, TypeError):
                return None

        allocation_set_id = request.query_params.get('allocation_set')
        try:
            allocation_set_id = int(allocation_set_id) if allocation_set_id else None
        except (ValueError, TypeError):
            allocation_set_id = None

        show_auto = request.query_params.get('show_auto', '0') not in ('', '0', 'false', 'False')
        return Response(ProgrammeRollupService.get_programme_rollup(
            version,
            allocation_set_id=allocation_set_id,
            programme_ids=_int_list(request.query_params.get('programmes')),
            project_ids=_int_list(request.query_params.get('projects')),
            show_auto=show_auto,
        ))

    # ── Snapshot lock helper ──────────────────────────────────────────────────

    def _snapshot_lock_check(self, version):
        """Return 423 Response if a snapshot job is in progress, else None."""
        from .models import ResourcePlanSnapshot
        snap = ResourcePlanSnapshot.objects.filter(
            version=version,
            status__in=[ResourcePlanSnapshot.STATUS_PENDING, ResourcePlanSnapshot.STATUS_IN_PROGRESS],
        ).first()
        if snap:
            return Response(
                {'detail': 'A snapshot is in progress. All write operations are locked.',
                 'snapshot_id': snap.pk},
                status=423,
            )
        return None

    # ── Snapshot endpoints (Phase 12) ─────────────────────────────────────────

    def snapshot_list(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        snaps = SnapshotService.list_snapshots(version)
        return Response([_serialise_snapshot(s) for s in snaps])

    def snapshot_create(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        label = (request.data.get('label') or '').strip()
        if not label:
            return Response({'label': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        notes = request.data.get('notes', '')
        try:
            snap = SnapshotService.create_snapshot_job(version, label, notes)
            return Response(_serialise_snapshot(snap), status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return Response({'detail': msg}, status=status.HTTP_409_CONFLICT)

    def snapshot_detail(self, request, plan_pk, pk, snap_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            snap = SnapshotService.get_snapshot(version, snap_pk)
        except Exception:
            return Response({'detail': 'Snapshot not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialise_snapshot(snap))

    def snapshot_delete(self, request, plan_pk, pk, snap_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            snap = SnapshotService.get_snapshot(version, snap_pk)
        except Exception:
            return Response({'detail': 'Snapshot not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            SnapshotService.delete_snapshot(snap)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DjangoValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return Response({'detail': msg}, status=status.HTTP_409_CONFLICT)

    def snapshot_allocations(self, request, plan_pk, pk, snap_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            snap = SnapshotService.get_snapshot(version, snap_pk)
        except Exception:
            return Response({'detail': 'Snapshot not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        PAGE_SIZE = 100
        qs = snap.allocations.all()
        total = qs.count()
        offset = (page - 1) * PAGE_SIZE
        rows = list(qs[offset:offset + PAGE_SIZE])
        return Response({
            'count': total,
            'page': page,
            'page_size': PAGE_SIZE,
            'total_pages': max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            'results': [_serialise_snap_alloc(r) for r in rows],
        })

    def snapshot_capacity(self, request, plan_pk, pk, snap_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            snap = SnapshotService.get_snapshot(version, snap_pk)
        except Exception:
            return Response({'detail': 'Snapshot not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
        PAGE_SIZE = 100
        qs = snap.capacities.all()
        total = qs.count()
        offset = (page - 1) * PAGE_SIZE
        rows = list(qs[offset:offset + PAGE_SIZE])
        return Response({
            'count': total,
            'page': page,
            'page_size': PAGE_SIZE,
            'total_pages': max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
            'results': [_serialise_snap_cap(r) for r in rows],
        })

    def snapshot_compare(self, request, plan_pk, pk, snap_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        a_id = request.query_params.get('a')
        b_id = request.query_params.get('b')
        if not a_id or not b_id:
            return Response({'detail': 'Query params a and b (snapshot IDs) are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            snap_a = SnapshotService.get_snapshot(version, a_id)
            snap_b = SnapshotService.get_snapshot(version, b_id)
        except Exception:
            return Response({'detail': 'One or both snapshots not found.'}, status=status.HTTP_404_NOT_FOUND)
        diff = SnapshotService.compare_snapshots(snap_a, snap_b)
        return Response({'snapshot_a': _serialise_snapshot(snap_a),
                         'snapshot_b': _serialise_snapshot(snap_b),
                         'diff': diff})

    # ── Export endpoint (Phase 14) ────────────────────────────────────────────

    def export_xlsx(self, request, plan_pk, pk):
        import io
        from django.http import HttpResponse
        from .services_export import ExportService

        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)

        allocation_set_id = request.query_params.get('allocation_set')
        try:
            allocation_set_id = int(allocation_set_id) if allocation_set_id else None
        except (ValueError, TypeError):
            allocation_set_id = None

        team_id = request.query_params.get('team')
        try:
            team_id = int(team_id) if team_id else None
        except (ValueError, TypeError):
            team_id = None

        wb = ExportService.build_workbook(version, allocation_set_id, team_id)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        plan_slug = version.plan.name.replace(' ', '_')[:40]
        filename  = f'{plan_slug}_v{version.version}_export.xlsx'
        resp = HttpResponse(
            buf.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp

    # ── Audit Log endpoints (Phase 13) ────────────────────────────────────────

    def audit_list(self, request, plan_pk, pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .services_audit import AuditLogService
        event_type = request.query_params.get('event_type', '').strip() or None
        date_from  = request.query_params.get('date_from', '').strip() or None
        date_to    = request.query_params.get('date_to', '').strip() or None
        try:
            page = int(request.query_params.get('page', 1))
        except (ValueError, TypeError):
            page = 1
        data = AuditLogService.list_logs(
            version, event_type=event_type, date_from=date_from, date_to=date_to, page=page
        )
        data['results'] = [_serialise_audit_log(e) for e in data['results']]
        return Response(data)

    def audit_detail(self, request, plan_pk, pk, audit_pk):
        version = self._get_version(plan_pk, pk)
        if not version:
            return Response({'detail': 'Version not found.'}, status=status.HTTP_404_NOT_FOUND)
        from .models import AuditLog
        try:
            entry = AuditLog.objects.select_related('engine_job').get(pk=audit_pk, version=version)
        except AuditLog.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialise_audit_log(entry, detail=True))


def _serialise_audit_log(entry, detail=False):
    d = {
        'id': entry.pk,
        'event_type': entry.event_type,
        'entity_type': entry.entity_type,
        'entity_id': entry.entity_id,
        'notes': entry.notes,
        'created_at': entry.created_at.isoformat(),
        'engine_job_id': entry.engine_job_id,
    }
    if detail:
        d['before_state'] = entry.before_state
        d['after_state']  = entry.after_state
    return d


def _serialise_snapshot(snap):
    return {
        'id': snap.pk,
        'label': snap.label,
        'notes': snap.notes,
        'status': snap.status,
        'total_allocation_days': float(snap.total_allocation_days) if snap.total_allocation_days is not None else None,
        'total_members': snap.total_members,
        'total_projects': snap.total_projects,
        'total_sprints': snap.total_sprints,
        'initiated_at': snap.initiated_at.isoformat() if snap.initiated_at else None,
        'completed_at': snap.completed_at.isoformat() if snap.completed_at else None,
        'error_log': snap.error_log,
    }


def _serialise_snap_alloc(r):
    return {
        'id': r.pk,
        'sprint_number': r.sprint_number,
        'sprint_name': r.sprint_name,
        'member_name': r.member_name,
        'team_name': r.team_name,
        'project_name': r.project_name,
        'programme_name': r.programme_name,
        'phase_name': r.phase_name,
        'assignment_type': r.assignment_type,
        'includes_in_budget': r.includes_in_budget,
        'days': float(r.days),
        'is_override': r.is_override,
        'is_placeholder': r.is_placeholder,
    }


def _serialise_snap_cap(r):
    return {
        'id': r.pk,
        'sprint_number': r.sprint_number,
        'sprint_name': r.sprint_name,
        'member_name': r.member_name,
        'team_name': r.team_name,
        'working_days': float(r.working_days),
        'holiday_days': float(r.holiday_days),
        'leave_days': float(r.leave_days),
        'placeholder_days': float(r.placeholder_days),
        'net_capacity': float(r.net_capacity),
    }


class PlanPhaseViewSet(viewsets.ViewSet):
    """Phase endpoints nested under version config."""

    def _get_version(self, pk):
        return ResourcePlanVersionConfigService.get_version(pk)

    # GET/POST /resource-plans/{plan_pk}/versions/{vpk}/projects/{epk}/teams/{tpk}/phases/
    @action(detail=True, methods=["get", "post"],
            url_path=r"projects/(?P<entry_pk>\d+)/teams/(?P<team_entry_pk>\d+)/phases")
    def phases(self, request, pk=None, entry_pk=None, team_entry_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            entry = ResourcePlanVersionConfigService.get_project_entry(version, entry_pk)
        except ResourcePlanVersionProject.DoesNotExist:
            return _entry_not_found()
        try:
            team_entry = entry.teams.get(pk=team_entry_pk)
        except ResourcePlanVersionProjectTeam.DoesNotExist:
            return _team_entry_not_found()

        if request.method == "GET":
            phases = PlanPhaseService.list_phases(team_entry)
            return Response(PlanPhaseSerializer(phases, many=True).data)

        # POST
        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            phase = PlanPhaseService.create_phase(
                team_entry,
                name=request.data.get("name", ""),
                sequence_order=request.data.get("sequence_order", 1),
                start_sprint_id=request.data.get("start_sprint") or None,
                end_sprint_id=request.data.get("end_sprint") or None,
                max_days_per_sprint=request.data.get("max_days_per_sprint"),
                ramp_pattern=request.data.get("ramp_pattern"),
                allow_multiple_engineers=request.data.get("allow_multiple_engineers", False),
                split_mode=request.data.get("split_mode"),
                notes=request.data.get("notes"),
            )
            return Response(PlanPhaseSerializer(phase).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET /resource-plans/{plan_pk}/versions/{vpk}/phases/options/
    @action(detail=True, methods=["get"], url_path="phases/options")
    def phases_options(self, request, pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        return Response(PlanPhaseService.get_phases_options(version))

    # GET/PATCH/DELETE /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/
    @action(detail=True, methods=["get", "patch", "delete"],
            url_path=r"phases/(?P<phase_pk>\d+)")
    def phase_detail(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            # Validate the phase belongs to this version
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        if request.method == "GET":
            return Response(PlanPhaseSerializer(phase).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            try:
                PlanPhaseService.delete_phase(phase)
                return Response(status=status.HTTP_204_NO_CONTENT)
            except DjangoValidationError as exc:
                detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages[0] if exc.messages else str(exc)}
                return Response(detail, status=status.HTTP_409_CONFLICT)

        # PATCH
        try:
            phase = PlanPhaseService.update_phase(
                phase,
                name=request.data.get("name"),
                sequence_order=request.data.get("sequence_order"),
                start_sprint_id=request.data.get("start_sprint"),
                end_sprint_id=request.data.get("end_sprint"),
                max_days_per_sprint=request.data.get("max_days_per_sprint"),
                ramp_pattern=request.data.get("ramp_pattern"),
                allow_multiple_engineers=request.data.get("allow_multiple_engineers"),
                split_mode=request.data.get("split_mode"),
                notes=request.data.get("notes"),
            )
            return Response(PlanPhaseSerializer(phase).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET/POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/segments/
    @action(detail=True, methods=["get", "post"],
            url_path=r"phases/(?P<phase_pk>\d+)/segments")
    def phase_segments(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        if request.method == "GET":
            segments = PlanPhaseService.list_segments(phase)
            return Response(PlanPhaseSegmentSerializer(segments, many=True).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            segment = PlanPhaseService.add_segment(
                phase,
                segment_type=request.data.get("segment_type"),
                start_pct=request.data.get("start_pct", 0),
                end_pct=request.data.get("end_pct", 100),
                duration=request.data.get("duration", 1),
                progression=request.data.get("progression"),
                step_count=request.data.get("step_count"),
            )
            return Response(PlanPhaseSegmentSerializer(segment).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/segments/suggest/
    @action(detail=True, methods=["post"],
            url_path=r"phases/(?P<phase_pk>\d+)/segments/suggest")
    def phase_segments_suggest(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        return Response(PlanPhaseService.suggest_segments(phase))

    # POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/segments/reorder/
    @action(detail=True, methods=["post"],
            url_path=r"phases/(?P<phase_pk>\d+)/segments/reorder")
    def phase_segments_reorder(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        order_list = request.data.get("order", [])
        PlanPhaseService.reorder_segments(phase, order_list)
        return Response({"detail": "Reordered."})

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/segments/{seg_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"phases/(?P<phase_pk>\d+)/segments/(?P<seg_pk>\d+)")
    def phase_segment_detail(self, request, pk=None, phase_pk=None, seg_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()
        try:
            segment = phase.segments.get(pk=seg_pk)
        except PlanPhaseSegment.DoesNotExist:
            return Response({"detail": "Segment not found."}, status=status.HTTP_404_NOT_FOUND)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            PlanPhaseService.delete_segment(segment)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            segment = PlanPhaseService.update_segment(
                segment,
                segment_type=request.data.get("segment_type"),
                start_pct=request.data.get("start_pct"),
                end_pct=request.data.get("end_pct"),
                duration=request.data.get("duration"),
                progression=request.data.get("progression"),
                step_count=request.data.get("step_count"),
            )
            return Response(PlanPhaseSegmentSerializer(segment).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET/POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/dependencies/
    @action(detail=True, methods=["get", "post"],
            url_path=r"phases/(?P<phase_pk>\d+)/dependencies")
    def phase_dependencies(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        if request.method == "GET":
            deps = PlanPhaseService.list_dependencies(phase)
            return Response(PlanPhaseDependencySerializer(deps, many=True).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            dep = PlanPhaseService.add_dependency(
                phase,
                predecessor_id=request.data.get("predecessor_phase"),
                dependency_type=request.data.get("dependency_type"),
                lag_sprints=request.data.get("lag_sprints", 0),
            )
            return Response(PlanPhaseDependencySerializer(dep).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/dependencies/{dep_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"phases/(?P<phase_pk>\d+)/dependencies/(?P<dep_pk>\d+)")
    def phase_dependency_detail(self, request, pk=None, phase_pk=None, dep_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()
        try:
            dep = phase.dependencies.get(pk=dep_pk)
        except PlanPhaseDependency.DoesNotExist:
            return Response({"detail": "Dependency not found."}, status=status.HTTP_404_NOT_FOUND)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            PlanPhaseService.delete_dependency(dep)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            dep = PlanPhaseService.update_dependency(
                dep,
                dependency_type=request.data.get("dependency_type"),
                lag_sprints=request.data.get("lag_sprints"),
            )
            return Response(PlanPhaseDependencySerializer(dep).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET/POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/pauses/
    @action(detail=True, methods=["get", "post"],
            url_path=r"phases/(?P<phase_pk>\d+)/pauses")
    def phase_pauses(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        if request.method == "GET":
            pauses = PlanPhaseService.list_pauses(phase)
            return Response(PlanPhasePauseSerializer(pauses, many=True).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            pause = PlanPhaseService.add_pause(
                phase,
                pause_from_id=request.data.get("pause_from"),
                input_mode=request.data.get("input_mode"),
                pause_until_sprint_id=request.data.get("pause_until_sprint") or None,
                pause_sprint_count=request.data.get("pause_sprint_count"),
                notes=request.data.get("notes"),
            )
            return Response(PlanPhasePauseSerializer(pause).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/pauses/{pause_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"phases/(?P<phase_pk>\d+)/pauses/(?P<pause_pk>\d+)")
    def phase_pause_detail(self, request, pk=None, phase_pk=None, pause_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()
        try:
            pause = phase.pauses.get(pk=pause_pk)
        except PlanPhasePause.DoesNotExist:
            return Response({"detail": "Pause not found."}, status=status.HTTP_404_NOT_FOUND)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            PlanPhaseService.delete_pause(pause)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            pause = PlanPhaseService.update_pause(
                pause,
                input_mode=request.data.get("input_mode"),
                pause_until_sprint_id=request.data.get("pause_until_sprint"),
                pause_sprint_count=request.data.get("pause_sprint_count"),
                notes=request.data.get("notes"),
            )
            return Response(PlanPhasePauseSerializer(pause).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # GET /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/assignments/options/
    @action(detail=True, methods=["get"],
            url_path=r"phases/(?P<phase_pk>\d+)/assignments/options")
    def phase_assignments_options(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()
        return Response(PlanAssignmentService.get_assignment_options(phase))

    # GET/POST /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/assignments/
    @action(detail=True, methods=["get", "post"],
            url_path=r"phases/(?P<phase_pk>\d+)/assignments")
    def phase_assignments(self, request, pk=None, phase_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()

        if request.method == "GET":
            assignments = PlanAssignmentService.list_assignments(phase)
            return Response(PlanAssignmentSerializer(assignments, many=True).data)

        lock = _snapshot_locked(version)
        if lock:
            return lock
        try:
            assignment = PlanAssignmentService.create_assignment(
                phase,
                team_member_id=request.data.get("team_member") or None,
                auto_assign=request.data.get("auto_assign", False),
                assignment_type=request.data.get("assignment_type"),
                replaces_member_id=request.data.get("replaces_member") or None,
                interim_sprint_count=request.data.get("interim_sprint_count"),
                split_value=request.data.get("split_value"),
                notes=request.data.get("notes"),
            )
            return Response(PlanAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)

    # PATCH/DELETE /resource-plans/{plan_pk}/versions/{vpk}/phases/{phase_pk}/assignments/{assign_pk}/
    @action(detail=True, methods=["patch", "delete"],
            url_path=r"phases/(?P<phase_pk>\d+)/assignments/(?P<assign_pk>\d+)")
    def phase_assignment_detail(self, request, pk=None, phase_pk=None, assign_pk=None, **kwargs):
        try:
            version = self._get_version(pk)
        except ResourcePlanVersion.DoesNotExist:
            return _version_not_found()
        try:
            phase = PlanPhaseService.get_phase(phase_pk)
            if phase.plan_project_team.plan_project.version_id != version.pk:
                return _phase_not_found()
        except PlanPhase.DoesNotExist:
            return _phase_not_found()
        try:
            assignment = phase.assignments.get(pk=assign_pk)
        except PlanAssignment.DoesNotExist:
            return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)

        lock = _snapshot_locked(version)
        if lock:
            return lock

        if request.method == "DELETE":
            PlanAssignmentService.delete_assignment(assignment)
            return Response(status=status.HTTP_204_NO_CONTENT)

        try:
            assignment = PlanAssignmentService.update_assignment(
                assignment,
                assignment_type=request.data.get("assignment_type"),
                team_member_id=request.data.get("team_member") or None,
                auto_assign=request.data.get("auto_assign"),
                replaces_member_id=request.data.get("replaces_member") or None,
                interim_sprint_count=request.data.get("interim_sprint_count"),
                split_value=request.data.get("split_value"),
                notes=request.data.get("notes"),
            )
            return Response(PlanAssignmentSerializer(assignment).data)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
