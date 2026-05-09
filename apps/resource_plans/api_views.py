import logging

from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
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
            comment_text = request.data.get("comment", "").strip()
            posted_by = request.data.get("posted_by", "Anonymous")
            try:
                comment = ResourcePlanCommentService.add_comment(plan, comment_text, posted_by)
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
