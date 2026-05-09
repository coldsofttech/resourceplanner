import logging
import threading
import uuid
from decimal import Decimal
from math import ceil as _ceil
from django.db import transaction, close_old_connections
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import ValidationError
from django.utils import timezone

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
    PlaceholderLeave,
)

_engine_logger = logging.getLogger("resource_plans.engine")


class ResourcePlanService:
    VALID_ORDER_FIELDS = {"name", "plan_type", "created_at", "updated_at"}
    _ORDER_FIELD_MAP = {"status": "version__status"}

    def list_plans(
        search=None,
        plan_type=None,
        version_status=None,
        fy_id=None,
        is_active=None,
        order_by="-created_at",
        page=1,
        page_size=20,
    ):
        qs = ResourcePlan.objects.filter(is_head=True).select_related(
            "version", "cloned_from"
        )

        if search:
            qs = qs.filter(name__icontains=search)
        if plan_type:
            qs = qs.filter(plan_type=plan_type)
        if version_status:
            # Filter by the status on the associated version
            qs = qs.filter(version__status=version_status)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if fy_id:
            qs = qs.filter(
                version__plan_group__in=ResourcePlanScope.objects.filter(
                    financial_year_id=fy_id
                ).values("plan_group")
            )

        prefix = "-" if order_by.startswith("-") else ""
        field = order_by.lstrip("-")
        field = ResourcePlanService._ORDER_FIELD_MAP.get(field, field)
        if (
            field not in ResourcePlanService.VALID_ORDER_FIELDS
            and field not in ResourcePlanService._ORDER_FIELD_MAP.values()
        ):
            order_by = "-created_at"
        else:
            order_by = prefix + field
        qs = qs.order_by(order_by)

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
    @transaction.atomic
    def create_plan(
        name,
        description,
        plan_type,
        financial_year_id,
        project_id=None,
        programme_id=None,
        team_id=None,
    ):
        # Name uniqueness (case-insensitive)
        if ResourcePlan.objects.filter(name__iexact=name).exists():
            raise ValidationError({"name": "A plan with this name already exists."})

        # Create plan
        plan = ResourcePlan.objects.create(
            name=name,
            description=description or None,
            plan_type=plan_type,
            financial_year_id=financial_year_id,
        )

        # Create version (group = new UUID, version = 1)
        plan_group = uuid.uuid4()
        threshold = Decimal("10.00")
        ResourcePlanVersion.objects.create(
            plan=plan,
            plan_group=plan_group,
            version=1,
            status=ResourcePlanVersion.STATUS_DRAFT,
            threshold_pct=threshold,
        )

        # Create scope
        ResourcePlanScope.objects.create(
            plan_group=plan_group,
            financial_year_id=financial_year_id,
            project_id=project_id or None,
            programme_id=programme_id or None,
            team_id=team_id or None,
        )

        return plan

    @staticmethod
    def list_stats(fields=None):
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = ResourcePlan.objects.filter(is_head=True)
        result = {}

        if wants("total_plans"):
            result["total_plans"] = qs.count()
        if wants("active_plans"):
            result["active_plans"] = qs.filter(is_active=True).count()
        if wants("draft_plans"):
            result["draft_plans"] = qs.filter(
                version__status=ResourcePlanVersion.STATUS_DRAFT
            ).count()
        if wants("locked_plans"):
            result["locked_plans"] = qs.filter(
                version__status=ResourcePlanVersion.STATUS_LOCKED
            ).count()

        return result

    @staticmethod
    def get_plan(plan_id: int):
        if not plan_id:
            raise ValidationError(
                "Invalid: plan_id must be a positive integer and greater than 0."
            )

        return ResourcePlan.objects.select_related("version", "cloned_from").get(
            pk=plan_id
        )

    @staticmethod
    @transaction.atomic
    def update_plan(
        plan, name=None, description=None, is_active=None, threshold_pct=None
    ):
        if plan.version.status != ResourcePlanVersion.STATUS_DRAFT:
            raise ValidationError("Only DRAFT plans can be edited.")

        if name and name != plan.name:
            if (
                ResourcePlan.objects.filter(name__iexact=name)
                .exclude(pk=plan.pk)
                .exists()
            ):
                raise ValidationError({"name": "A plan with this name already exists."})
            plan.name = name

        if description is not None:
            plan.description = description or None

        plan.save()

        if threshold_pct is not None:
            from decimal import Decimal, InvalidOperation

            try:
                pct = Decimal(str(threshold_pct))
                if pct < 0 or pct > 100:
                    raise ValidationError(
                        {"threshold_pct": "Threshold must be between 0 and 100."}
                    )
                plan.version.threshold_pct = pct
                plan.version.save(update_fields=["threshold_pct"])
            except (ValueError, InvalidOperation):
                raise ValidationError({"threshold_pct": "Invalid threshold value."})

        if is_active is not None:
            (
                ResourcePlanService.unarchive_plan(plan)
                if is_active
                else ResourcePlanService.archive_plan(plan)
            )

        return plan

    @staticmethod
    @transaction.atomic
    def delete_plan(plan):
        if plan.version.status != ResourcePlanVersion.STATUS_DRAFT:
            raise ValidationError("Only DRAFT plans can be deleted.")
        plan.delete()

    @staticmethod
    @transaction.atomic
    def activate_plan(plan):
        if plan.version.status not in (
            ResourcePlanVersion.STATUS_DRAFT,
            ResourcePlanVersion.STATUS_LOCKED,
        ):
            raise ValidationError("Only DRAFT or LOCKED plans can be activated.")

        plan_group = plan.version.plan_group

        # Auto-supersede previous ACTIVE version in same group
        ResourcePlanVersion.objects.filter(
            plan_group=plan_group,
            status=ResourcePlanVersion.STATUS_ACTIVE,
        ).exclude(plan=plan).update(status=ResourcePlanVersion.STATUS_SUPERSEDED)

        plan.version.status = ResourcePlanVersion.STATUS_ACTIVE
        plan.version.save(update_fields=["status"])
        return plan

    @staticmethod
    @transaction.atomic
    def lock_plan(plan):
        if plan.version.status != ResourcePlanVersion.STATUS_ACTIVE:
            raise ValidationError("Only ACTIVE plans can be locked.")
        plan.version.status = ResourcePlanVersion.STATUS_LOCKED
        plan.version.save(update_fields=["status"])
        return plan

    @staticmethod
    @transaction.atomic
    def clone_plan(plan, new_name, include_config=False):
        """Clone into a new plan_group with version 1 and a new scope record.
        If include_config=True, the latest version's configuration is deep-copied.
        """
        if ResourcePlan.objects.filter(name__iexact=new_name).exists():
            raise ValidationError({"name": "A plan with this name already exists."})

        source_version = plan.version
        source_scope = ResourcePlanScope.objects.get(
            plan_group=source_version.plan_group
        )

        new_plan = ResourcePlan.objects.create(
            name=new_name,
            description=plan.description,
            plan_type=plan.plan_type,
            financial_year_id=source_scope.financial_year_id,
            cloned_from=plan,
        )

        new_group = uuid.uuid4()
        new_version = ResourcePlanVersion.objects.create(
            plan=new_plan,
            plan_group=new_group,
            version=1,
            threshold_pct=source_version.threshold_pct,
        )

        ResourcePlanScope.objects.create(
            plan_group=new_group,
            financial_year_id=source_scope.financial_year_id,
            project_id=source_scope.project_id,
            programme_id=source_scope.programme_id,
            team_id=source_scope.team_id,
        )

        if include_config:
            _deep_copy_version_config(source_version, new_version)

        return new_plan

    @staticmethod
    @transaction.atomic
    def archive_plan(plan):
        plan.is_active = False
        plan.save(update_fields=["is_active", "updated_at"])
        return plan

    @staticmethod
    @transaction.atomic
    def unarchive_plan(plan):
        plan.is_active = True
        plan.save(update_fields=["is_active", "updated_at"])
        return plan

    @staticmethod
    @transaction.atomic
    def new_version(plan, threshold_pct=None):
        """Create a new DRAFT version in the same plan_group, becoming the new head."""
        from decimal import Decimal, InvalidOperation

        source_version = plan.version
        plan_group = source_version.plan_group

        max_v = (
            ResourcePlanVersion.objects.filter(plan_group=plan_group)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        ) or 0

        # Resolve threshold
        if threshold_pct is not None:
            try:
                new_threshold = Decimal(str(threshold_pct))
                if not (0 <= new_threshold <= 100):
                    raise ValidationError(
                        {"threshold_pct": "Threshold must be between 0 and 100."}
                    )
            except InvalidOperation:
                raise ValidationError({"threshold_pct": "Invalid threshold value."})
        else:
            new_threshold = source_version.threshold_pct

        # Find current head to transfer ownership
        current_head = (
            ResourcePlan.objects.select_for_update()
            .filter(version__plan_group=plan_group, is_head=True)
            .first()
        )
        original_name = current_head.name if current_head else plan.name
        source_description = (
            current_head.description if current_head else plan.description
        )
        source_plan_type = current_head.plan_type if current_head else plan.plan_type
        source_fy = current_head.financial_year if current_head else plan.financial_year

        # Rename current head to free up the original name
        if current_head:
            head_v_num = current_head.version.version
            renamed = f"{original_name} (v{head_v_num})"
            counter = 2
            while (
                ResourcePlan.objects.filter(name__iexact=renamed)
                .exclude(pk=current_head.pk)
                .exists()
            ):
                renamed = f"{original_name} (v{head_v_num}.{counter})"
                counter += 1
            current_head.name = renamed
            current_head.is_head = False
            current_head.save(update_fields=["name", "is_head"])

        new_plan = ResourcePlan.objects.create(
            name=original_name,
            description=source_description,
            plan_type=source_plan_type,
            financial_year=source_fy,
            is_head=True,
        )

        ResourcePlanVersion.objects.create(
            plan=new_plan,
            plan_group=plan_group,
            version=max_v + 1,
            threshold_pct=new_threshold,
        )

        return new_plan

    @staticmethod
    @transaction.atomic
    def restore_version(source_plan, include_config=False):
        """Restore source_plan as a new DRAFT version in the same plan_group, becoming the new head.
        If include_config=True, the source version's configuration is deep-copied into the new version.
        """
        source_version = source_plan.version
        plan_group = source_version.plan_group

        max_v = (
            ResourcePlanVersion.objects.filter(plan_group=plan_group)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        ) or 0

        # Find current head to transfer ownership
        current_head = (
            ResourcePlan.objects.select_for_update()
            .filter(version__plan_group=plan_group, is_head=True)
            .first()
        )
        original_name = current_head.name if current_head else source_plan.name

        # Rename current head to free up the original name
        if current_head:
            head_v_num = current_head.version.version
            renamed = f"{original_name} (v{head_v_num})"
            counter = 2
            while (
                ResourcePlan.objects.filter(name__iexact=renamed)
                .exclude(pk=current_head.pk)
                .exists()
            ):
                renamed = f"{original_name} (v{head_v_num}.{counter})"
                counter += 1
            current_head.name = renamed
            current_head.is_head = False
            current_head.save(update_fields=["name", "is_head"])

        new_plan = ResourcePlan.objects.create(
            name=original_name,
            description=source_plan.description,
            plan_type=source_plan.plan_type,
            financial_year=source_plan.financial_year,
            is_head=True,
        )

        new_version = ResourcePlanVersion.objects.create(
            plan=new_plan,
            plan_group=plan_group,
            version=max_v + 1,
            cloned_from=source_version,
            threshold_pct=source_version.threshold_pct,
        )

        if include_config:
            _deep_copy_version_config(source_version, new_version)

        return new_plan

    @staticmethod
    def get_versions(plan, page=1, page_size=20):
        plan_group = plan.version.plan_group
        qs = (
            ResourcePlanVersion.objects.filter(plan_group=plan_group)
            .select_related("plan", "cloned_from__plan")
            .order_by("-version")
        )

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
    def check_name_unique(name, exclude_pk=None):
        qs = ResourcePlan.objects.filter(name__iexact=name)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return not qs.exists()

    @staticmethod
    def expire_plans_for_fy(fy):
        """Mark DRAFT/ACTIVE/LOCKED versions scoped to this FY as EXPIRED."""
        plan_groups = ResourcePlanScope.objects.filter(financial_year=fy).values_list(
            "plan_group", flat=True
        )
        ResourcePlanVersion.objects.filter(
            plan_group__in=plan_groups,
            status__in=[
                ResourcePlanVersion.STATUS_DRAFT,
                ResourcePlanVersion.STATUS_ACTIVE,
                ResourcePlanVersion.STATUS_LOCKED,
            ],
        ).update(status=ResourcePlanVersion.STATUS_EXPIRED)

    @staticmethod
    def expire_plans_for_project(project):
        plan_groups = ResourcePlanScope.objects.filter(project=project).values_list(
            "plan_group", flat=True
        )
        ResourcePlanVersion.objects.filter(
            plan_group__in=plan_groups,
            status__in=[
                ResourcePlanVersion.STATUS_DRAFT,
                ResourcePlanVersion.STATUS_ACTIVE,
                ResourcePlanVersion.STATUS_LOCKED,
            ],
        ).update(status=ResourcePlanVersion.STATUS_EXPIRED)

    @staticmethod
    def expire_plans_for_programme(programme):
        plan_groups = ResourcePlanScope.objects.filter(programme=programme).values_list(
            "plan_group", flat=True
        )
        ResourcePlanVersion.objects.filter(
            plan_group__in=plan_groups,
            status__in=[
                ResourcePlanVersion.STATUS_DRAFT,
                ResourcePlanVersion.STATUS_ACTIVE,
                ResourcePlanVersion.STATUS_LOCKED,
            ],
        ).update(status=ResourcePlanVersion.STATUS_EXPIRED)


class ResourcePlanVersionService:
    @staticmethod
    def get_for_plan(plan):
        return plan.version

    @staticmethod
    def get_group_versions(plan_group, page=1, page_size=20):
        qs = (
            ResourcePlanVersion.objects.filter(plan_group=plan_group)
            .select_related("plan", "cloned_from__plan")
            .order_by("-version")
        )

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


class ResourcePlanScopeService:
    @staticmethod
    def get_for_plan(plan):
        plan_group = plan.version.plan_group
        return ResourcePlanScope.objects.select_related(
            "financial_year", "project", "programme", "team"
        ).get(plan_group=plan_group)

    @staticmethod
    def get_options():
        from apps.financial_years.models import FinancialYear
        from apps.projects.models import Project
        from apps.programmes.models import Programme
        from apps.delivery_teams.models import DeliveryTeam

        return {
            "financial_years": list(
                FinancialYear.objects.order_by("-start_date").values(
                    "id", "long_fy", "short_fy"
                )
            ),
            "projects": list(
                Project.objects.filter(status__in=["NEW", "IN_PROGRESS", "ON_HOLD"])
                .order_by("name")
                .values("id", "name")
            ),
            "programmes": list(Programme.objects.order_by("name").values("id", "name")),
            "teams": list(DeliveryTeam.objects.order_by("name").values("id", "name")),
            "plan_type_choices": [
                {"value": k, "label": v} for k, v in ResourcePlan.PLAN_TYPE_CHOICES
            ],
            "status_choices": [
                {"value": k, "label": v}
                for k, v in ResourcePlanVersion.STATUS_CHOICES
                if k != ResourcePlanVersion.STATUS_SUPERSEDED
                and k != ResourcePlanVersion.STATUS_EXPIRED
            ],
        }


class ResourcePlanCommentService:
    @staticmethod
    def list_comments(plan, page=1, page_size=20):
        qs = plan.comments.all()

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
    def add_comment(plan, comment_text, posted_by="Anonymous"):
        if not comment_text or not comment_text.strip():
            raise ValidationError({"comment": "Comment text is required."})
        return ResourcePlanComment.objects.create(
            plan=plan,
            comment=comment_text.strip(),
            posted_by=(posted_by or "Anonymous").strip() or "Anonymous",
        )


def _get_sprint_point_price():
    """Return SPP from Configurations.SPRINT_POINT_PRICE, fallback 1150."""
    from apps.configurations.services import ConfigurationService

    return Decimal(
        str(ConfigurationService.get_float("SPRINT_POINT_PRICE", fallback=1150.0))
    )


def _round_up_quarter(value):
    """Round a float/Decimal up to the nearest 0.25."""
    return Decimal(str(_ceil(float(value) * 4) / 4))


def _compute_days_required(basis_amount, sprint_point_price):
    if basis_amount is None or sprint_point_price is None or sprint_point_price == 0:
        return None
    return _round_up_quarter(
        Decimal(str(basis_amount)) / Decimal(str(sprint_point_price))
    )


def _compute_team_allocated_days(team_entry, plan_project):
    spp = _get_sprint_point_price()
    if team_entry.allocation_type == ResourcePlanVersionProjectTeam.ALLOC_PERCENT:
        if plan_project.days_required is None or team_entry.allocation_pct is None:
            return None
        return (team_entry.allocation_pct / Decimal("100")) * plan_project.days_required
    if team_entry.allocation_type == ResourcePlanVersionProjectTeam.ALLOC_DAYS:
        return team_entry.allocation_days
    if team_entry.allocation_type == ResourcePlanVersionProjectTeam.ALLOC_BUDGET:
        return _compute_days_required(team_entry.allocation_budget, spp)
    return None


def _recompute_project_flags(plan_project):
    teams = list(plan_project.teams.all())
    total = sum(t.allocated_days or Decimal("0") for t in teams)
    dr = plan_project.days_required

    plan_project.is_over_threshold = bool(dr is not None and total > dr)
    plan_project.is_under_threshold = bool(dr is not None and total < dr)

    budget_teams = [
        t
        for t in teams
        if t.allocation_type == ResourcePlanVersionProjectTeam.ALLOC_BUDGET
    ]
    if budget_teams and plan_project.basis_amount is not None:
        budget_sum = sum(t.allocation_budget or Decimal("0") for t in budget_teams)
        plan_project.is_team_budget_mismatch = budget_sum.quantize(
            Decimal("0.01")
        ) != Decimal(str(plan_project.basis_amount)).quantize(Decimal("0.01"))
    else:
        plan_project.is_team_budget_mismatch = False

    pct_teams = [
        t
        for t in teams
        if t.allocation_type == ResourcePlanVersionProjectTeam.ALLOC_PERCENT
    ]
    if pct_teams:
        pct_sum = sum(t.allocation_pct or Decimal("0") for t in pct_teams)
        plan_project.is_percent_incomplete = pct_sum != Decimal("100")
    else:
        plan_project.is_percent_incomplete = False

    plan_project.save(
        update_fields=[
            "is_over_threshold",
            "is_under_threshold",
            "is_team_budget_mismatch",
            "is_percent_incomplete",
        ]
    )


class ResourcePlanVersionConfigService:

    @staticmethod
    def get_version(version_pk):
        return ResourcePlanVersion.objects.select_related("plan").get(pk=version_pk)

    @staticmethod
    def list_projects(version, page=1, page_size=20, search=None, programme_id=None):
        qs = version.projects.select_related("project__programme").prefetch_related(
            "teams", "budget_releases"
        )
        if search:
            qs = qs.filter(project__name__icontains=search)
        if programme_id:
            qs = qs.filter(project__programme_id=programme_id)
        qs = qs.order_by("display_order", "created_at")

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": list(page_obj.object_list),
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    @transaction.atomic
    def add_project(
        version,
        project_id,
        basis,
        basis_amount=None,
        priority_override=None,
        confidence_override=None,
        estimate_id=None,
    ):
        from apps.projects.models import Project, ProjectBudget, ProjectEstimate

        if ResourcePlanVersionProject.objects.filter(
            version=version, project_id=project_id
        ).exists():
            raise ValidationError(
                {"project": "Project is already in this plan version."}
            )

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise ValidationError({"project": "Project not found."})

        snapshotted_budget = None
        snapshotted_estimate = None
        synced_amount = None

        if basis == ResourcePlanVersionProject.BASIS_BUDGET:
            fy_id = (
                ResourcePlanScope.objects.filter(plan_group=version.plan_group)
                .values_list("financial_year_id", flat=True)
                .first()
            )
            budget = ProjectBudget.objects.filter(
                project=project, financial_year_id=fy_id
            ).first()
            if budget and budget.actual_budget is not None:
                snapshotted_budget = budget
                synced_amount = Decimal(str(budget.actual_budget))
        elif basis == ResourcePlanVersionProject.BASIS_ESTIMATE:
            if estimate_id:
                try:
                    estimate = ProjectEstimate.objects.get(pk=estimate_id, project=project)
                except ProjectEstimate.DoesNotExist:
                    estimate = None
            else:
                estimate = (
                    ProjectEstimate.objects.filter(project=project, is_active=True)
                    .order_by("-version")
                    .first()
                )
            if estimate:
                snapshotted_estimate = estimate
                synced_amount = estimate.total_cost
        elif basis == ResourcePlanVersionProject.BASIS_CUSTOM:
            if basis_amount is not None:
                synced_amount = Decimal(str(basis_amount))

        days_req = _compute_days_required(synced_amount, _get_sprint_point_price())

        entry = ResourcePlanVersionProject.objects.create(
            version=version,
            project=project,
            basis=basis,
            basis_amount=synced_amount,
            basis_synced_at=timezone.now() if synced_amount is not None else None,
            snapshotted_budget=snapshotted_budget,
            snapshotted_estimate=snapshotted_estimate,
            days_required=days_req,
            priority_snapshot=project.priority or None,
            confidence_snapshot=project.confidence or None,
            priority_override=priority_override or None,
            confidence_override=confidence_override or None,
            display_order=version.projects.count(),
        )
        return entry

    @staticmethod
    def get_project_entry(version, entry_pk):
        return ResourcePlanVersionProject.objects.select_related(
            "project__programme",
            "version",
            "start_sprint",
            "end_sprint",
            "snapshotted_budget",
            "snapshotted_estimate",
        ).get(pk=entry_pk, version=version)

    @staticmethod
    @transaction.atomic
    def update_project_entry(
        entry,
        basis=None,
        basis_amount=None,
        priority_override=None,
        confidence_override=None,
        start_sprint_id=None,
        end_sprint_id=None,
        dates_strict=None,
        budget_release_mode=None,
        estimate_id=None,
    ):
        changed_basis = False

        if basis is not None and basis != entry.basis:
            entry.basis = basis
            changed_basis = True

        if (
            basis == ResourcePlanVersionProject.BASIS_CUSTOM
            and basis_amount is not None
        ):
            entry.basis_amount = Decimal(str(basis_amount))
            entry.basis_synced_at = timezone.now()
            entry.snapshotted_budget = None
            entry.snapshotted_estimate = None
            changed_basis = True
        elif changed_basis and basis != ResourcePlanVersionProject.BASIS_CUSTOM:
            ResourcePlanVersionConfigService._do_resync(entry, estimate_id=estimate_id)
            return entry

        if priority_override is not None:
            entry.priority_override = priority_override or None
        if confidence_override is not None:
            entry.confidence_override = confidence_override or None
        if start_sprint_id is not None:
            entry.start_sprint_id = start_sprint_id or None
        if end_sprint_id is not None:
            entry.end_sprint_id = end_sprint_id or None
        if dates_strict is not None:
            entry.dates_strict = dates_strict

        old_mode = entry.budget_release_mode
        if budget_release_mode is not None:
            entry.budget_release_mode = budget_release_mode or None
            if entry.budget_release_mode != old_mode:
                entry.budget_releases.all().delete()

        if changed_basis:
            entry.days_required = _compute_days_required(
                entry.basis_amount, _get_sprint_point_price()
            )
            _update_team_days_for_entry(entry)

        entry.save()
        _recompute_project_flags(entry)
        return entry

    @staticmethod
    @transaction.atomic
    def delete_project_entry(entry):
        entry.delete()

    @staticmethod
    @transaction.atomic
    def resync_project(entry):
        ResourcePlanVersionConfigService._do_resync(entry)
        _recompute_project_flags(entry)
        return entry

    @staticmethod
    def _do_resync(entry, estimate_id=None):
        from apps.projects.models import ProjectBudget, ProjectEstimate

        if entry.basis == ResourcePlanVersionProject.BASIS_BUDGET:
            fy_id = (
                ResourcePlanScope.objects.filter(plan_group=entry.version.plan_group)
                .values_list("financial_year_id", flat=True)
                .first()
            )
            budget = ProjectBudget.objects.filter(
                project=entry.project, financial_year_id=fy_id
            ).first()
            if budget and budget.actual_budget is not None:
                entry.snapshotted_budget = budget
                entry.snapshotted_estimate = None
                entry.basis_amount = Decimal(str(budget.actual_budget))
            else:
                entry.basis_amount = None

        elif entry.basis == ResourcePlanVersionProject.BASIS_ESTIMATE:
            if estimate_id:
                try:
                    estimate = ProjectEstimate.objects.get(pk=estimate_id, project=entry.project)
                except ProjectEstimate.DoesNotExist:
                    estimate = None
            else:
                estimate = (
                    ProjectEstimate.objects.filter(project=entry.project, is_active=True)
                    .order_by("-version")
                    .first()
                )
            if estimate:
                entry.snapshotted_estimate = estimate
                entry.snapshotted_budget = None
                entry.basis_amount = estimate.total_cost
            else:
                entry.basis_amount = None
        else:
            return

        entry.basis_synced_at = timezone.now()
        entry.days_required = _compute_days_required(
            entry.basis_amount, _get_sprint_point_price()
        )
        entry.save(
            update_fields=[
                "snapshotted_budget",
                "snapshotted_estimate",
                "basis_amount",
                "basis_synced_at",
                "days_required",
            ]
        )
        _update_team_days_for_entry(entry)

    @staticmethod
    def get_unmapped_projects(version, search=None):
        from apps.projects.models import Project

        mapped_ids = version.projects.values_list("project_id", flat=True)
        qs = (
            Project.objects.filter(is_active=True)
            .exclude(id__in=mapped_ids)
            .select_related("programme")
            .order_by("programme__name", "name")
        )
        if search:
            qs = qs.filter(name__icontains=search)

        groups = {}
        for p in qs:
            key = p.programme.name if p.programme else "Others"
            prog_id = p.programme_id
            if key not in groups:
                groups[key] = {
                    "programme": key,
                    "programme_id": prog_id,
                    "projects": [],
                }
            groups[key]["projects"].append(
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status,
                    "priority": p.priority,
                    "confidence": p.confidence,
                }
            )
        return list(groups.values())

    @staticmethod
    def get_options(version):
        from apps.sprints.models import Sprint
        from apps.programmes.models import Programme

        fy_id = (
            ResourcePlanScope.objects.filter(plan_group=version.plan_group)
            .values_list("financial_year_id", flat=True)
            .first()
        )

        sprints = []
        if fy_id:
            sprints = list(
                Sprint.objects.filter(financial_year_id=fy_id)
                .order_by("sprint_number")
                .values(
                    "id",
                    "sprint_name",
                    "sprint_number",
                    "start_date",
                    "end_date",
                    "month",
                )
            )

        return {
            "priority_choices": [
                {"value": "VERY_HIGH", "label": "Very High"},
                {"value": "HIGH", "label": "High"},
                {"value": "MEDIUM", "label": "Medium"},
                {"value": "LOW", "label": "Low"},
            ],
            "confidence_choices": [
                {"value": "VERY_HIGH", "label": "Very High"},
                {"value": "HIGH", "label": "High"},
                {"value": "MEDIUM", "label": "Medium"},
                {"value": "LOW", "label": "Low"},
            ],
            "basis_choices": [
                {"value": c[0], "label": c[1]}
                for c in ResourcePlanVersionProject.BASIS_CHOICES
            ],
            "allocation_type_choices": [
                {"value": c[0], "label": c[1]}
                for c in ResourcePlanVersionProjectTeam.ALLOC_CHOICES
            ],
            "budget_release_mode_choices": (
                [{"value": "", "label": "None"}]
                + [
                    {"value": c[0], "label": c[1]}
                    for c in ResourcePlanVersionProject.BUDGET_RELEASE_CHOICES
                ]
            ),
            "sprints": sprints,
            "financial_year_id": fy_id,
            "programmes": list(
                Programme.objects.filter(
                    id__in=version.projects.exclude(project__programme__isnull=True)
                    .values_list("project__programme_id", flat=True)
                    .distinct()
                )
                .order_by("name")
                .values("id", "name")
            ),
        }

    @staticmethod
    def reorder_project(entry, display_order):
        try:
            display_order = int(display_order)
        except (TypeError, ValueError):
            raise ValidationError({"display_order": "Must be a non-negative integer."})
        entry.display_order = display_order
        entry.save(update_fields=["display_order"])
        return entry

    # ── Budget Releases ───────────────────────────────────────────────────────

    @staticmethod
    def list_budget_releases(entry):
        return list(entry.budget_releases.select_related("sprint").all())

    @staticmethod
    @transaction.atomic
    def add_budget_release(
        entry, entry_type, amount, sprint_id=None, month=None, notes=None
    ):
        if not entry.budget_release_mode:
            raise ValidationError(
                {"entry_type": "Set budget_release_mode on the project first."}
            )
        if entry_type != entry.budget_release_mode:
            raise ValidationError(
                {
                    "entry_type": f"Must match project budget_release_mode: {entry.budget_release_mode}."
                }
            )

        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than 0."})

        ResourcePlanVersionConfigService._validate_release_sum(entry, amount)

        if entry_type == ResourcePlanVersionProjectBudgetRelease.ENTRY_SPRINT:
            if not sprint_id:
                raise ValidationError({"sprint": "Sprint is required."})
            if entry.budget_releases.filter(
                entry_type=entry_type, sprint_id=sprint_id
            ).exists():
                raise ValidationError(
                    {"sprint": "A release for this sprint already exists."}
                )
            return ResourcePlanVersionProjectBudgetRelease.objects.create(
                plan_project=entry,
                entry_type=entry_type,
                sprint_id=sprint_id,
                amount=amount,
                notes=notes or None,
            )
        else:
            if not month:
                raise ValidationError({"month": "Month is required."})
            if entry.budget_releases.filter(
                entry_type=entry_type, month=month
            ).exists():
                raise ValidationError(
                    {"month": f"A release for {month} already exists."}
                )
            return ResourcePlanVersionProjectBudgetRelease.objects.create(
                plan_project=entry,
                entry_type=entry_type,
                month=month,
                amount=amount,
                notes=notes or None,
            )

    @staticmethod
    @transaction.atomic
    def update_budget_release(release, amount=None, notes=None):
        if amount is not None:
            amount = Decimal(str(amount))
            if amount <= 0:
                raise ValidationError({"amount": "Amount must be greater than 0."})
            ResourcePlanVersionConfigService._validate_release_sum(
                release.plan_project, amount, exclude_pk=release.pk
            )
            release.amount = amount
        if notes is not None:
            release.notes = notes or None
        release.save()
        return release

    @staticmethod
    @transaction.atomic
    def delete_budget_release(release):
        release.delete()

    @staticmethod
    def _validate_release_sum(entry, new_amount, exclude_pk=None):
        if entry.basis_amount is None:
            return
        qs = entry.budget_releases.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        existing_sum = sum(r.amount for r in qs) if qs.exists() else Decimal("0")
        if existing_sum + new_amount > entry.basis_amount:
            raise ValidationError(
                {
                    "amount": f"Total releases (£{existing_sum + new_amount:,.2f}) would exceed basis amount (£{entry.basis_amount:,.2f})."
                }
            )

    # ── Teams ─────────────────────────────────────────────────────────────────

    @staticmethod
    def list_teams(entry):
        return list(entry.teams.select_related("team").all())

    @staticmethod
    @transaction.atomic
    def add_team(entry, team_id, allocation_type, value, sequence_order=1):
        from apps.delivery_teams.models import DeliveryTeam

        if entry.teams.filter(team_id=team_id).exists():
            raise ValidationError({"team": "Team already assigned to this project."})

        try:
            team = DeliveryTeam.objects.get(pk=team_id)
        except DeliveryTeam.DoesNotExist:
            raise ValidationError({"team": "Team not found."})

        value = Decimal(str(value))
        kwargs = {"allocation_type": allocation_type, "sequence_order": sequence_order}
        if allocation_type == ResourcePlanVersionProjectTeam.ALLOC_PERCENT:
            if value < 0 or value > 100:
                raise ValidationError({"value": "Percent must be between 0 and 100."})
            kwargs["allocation_pct"] = value
        elif allocation_type == ResourcePlanVersionProjectTeam.ALLOC_DAYS:
            if value < 0:
                raise ValidationError({"value": "Days must be >= 0."})
            kwargs["allocation_days"] = value
        elif allocation_type == ResourcePlanVersionProjectTeam.ALLOC_BUDGET:
            if value < 0:
                raise ValidationError({"value": "Budget must be >= 0."})
            kwargs["allocation_budget"] = value
        else:
            raise ValidationError({"allocation_type": "Invalid allocation type."})

        team_entry = ResourcePlanVersionProjectTeam.objects.create(
            plan_project=entry, team=team, **kwargs
        )
        team_entry.allocated_days = _compute_team_allocated_days(team_entry, entry)
        team_entry.save(update_fields=["allocated_days"])
        _recompute_project_flags(entry)
        return team_entry

    @staticmethod
    @transaction.atomic
    def update_team(team_entry, allocation_type=None, value=None, sequence_order=None):
        if allocation_type is not None:
            team_entry.allocation_type = allocation_type
            team_entry.allocation_pct = None
            team_entry.allocation_days = None
            team_entry.allocation_budget = None

        if value is not None:
            value = Decimal(str(value))
            atype = team_entry.allocation_type
            if atype == ResourcePlanVersionProjectTeam.ALLOC_PERCENT:
                if value < 0 or value > 100:
                    raise ValidationError(
                        {"value": "Percent must be between 0 and 100."}
                    )
                team_entry.allocation_pct = value
                team_entry.allocation_days = None
                team_entry.allocation_budget = None
            elif atype == ResourcePlanVersionProjectTeam.ALLOC_DAYS:
                team_entry.allocation_days = value
                team_entry.allocation_pct = None
                team_entry.allocation_budget = None
            elif atype == ResourcePlanVersionProjectTeam.ALLOC_BUDGET:
                team_entry.allocation_budget = value
                team_entry.allocation_pct = None
                team_entry.allocation_days = None

        if sequence_order is not None:
            team_entry.sequence_order = int(sequence_order)

        team_entry.allocated_days = _compute_team_allocated_days(
            team_entry, team_entry.plan_project
        )
        team_entry.save()
        _recompute_project_flags(team_entry.plan_project)
        return team_entry

    @staticmethod
    @transaction.atomic
    def delete_team(team_entry):
        plan_project = team_entry.plan_project
        team_entry.delete()
        _recompute_project_flags(plan_project)

    @staticmethod
    def get_team_options(entry):
        from apps.delivery_teams.models import DeliveryTeam

        assigned_ids = entry.teams.values_list("team_id", flat=True)
        teams = (
            DeliveryTeam.objects.filter(is_active=True)
            .exclude(id__in=assigned_ids)
            .order_by("name")
        )
        return [{"id": t.id, "name": t.name} for t in teams]


def _update_team_days_for_entry(entry):
    """Recompute allocated_days for all teams of a project entry."""
    for t in entry.teams.all():
        t.allocated_days = _compute_team_allocated_days(t, entry)
        t.save(update_fields=["allocated_days"])


class PlanPhaseService:

    @staticmethod
    def list_phases(team_entry):
        return list(
            PlanPhase.objects.filter(plan_project_team=team_entry)
            .select_related("start_sprint", "end_sprint")
            .prefetch_related("segments", "dependencies", "pauses")
            .order_by("sequence_order")
        )

    @staticmethod
    def get_phase(pk):
        return PlanPhase.objects.select_related(
            "plan_project_team__plan_project__project",
            "start_sprint", "end_sprint",
        ).get(pk=pk)

    @staticmethod
    @transaction.atomic
    def create_phase(team_entry, name, sequence_order=1, start_sprint_id=None,
                     end_sprint_id=None, max_days_per_sprint=None, ramp_pattern=None,
                     allow_multiple_engineers=False, split_mode=None, notes=None):
        if not name or not name.strip():
            raise ValidationError({"name": "Phase name is required."})
        name = name.strip()

        # Uniqueness: name must be unique at project level (across all teams for same project in same version)
        project = team_entry.plan_project.project
        version = team_entry.plan_project.version
        if PlanPhase.objects.filter(
            plan_project_team__plan_project__version=version,
            plan_project_team__plan_project__project=project,
            name__iexact=name,
        ).exists():
            raise ValidationError({"name": "A phase with this name already exists for this project."})

        kwargs = {
            "plan_project_team": team_entry,
            "name": name,
            "sequence_order": sequence_order or 1,
            "allow_multiple_engineers": bool(allow_multiple_engineers),
            "ramp_pattern": ramp_pattern or PlanPhase.RAMP_FLAT,
            "split_mode": split_mode or PlanPhase.SPLIT_AUTO,
        }
        if start_sprint_id:
            kwargs["start_sprint_id"] = start_sprint_id
        if end_sprint_id:
            kwargs["end_sprint_id"] = end_sprint_id
        if max_days_per_sprint is not None:
            from decimal import Decimal
            kwargs["max_days_per_sprint"] = Decimal(str(max_days_per_sprint))
        if notes:
            kwargs["notes"] = notes

        return PlanPhase.objects.create(**kwargs)

    @staticmethod
    @transaction.atomic
    def update_phase(phase, name=None, sequence_order=None, start_sprint_id=None,
                     end_sprint_id=None, max_days_per_sprint=None, ramp_pattern=None,
                     allow_multiple_engineers=None, split_mode=None, notes=None):
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationError({"name": "Phase name is required."})
            if name.lower() != phase.name.lower():
                project = phase.plan_project_team.plan_project.project
                version = phase.plan_project_team.plan_project.version
                if PlanPhase.objects.filter(
                    plan_project_team__plan_project__version=version,
                    plan_project_team__plan_project__project=project,
                    name__iexact=name,
                ).exclude(pk=phase.pk).exists():
                    raise ValidationError({"name": "A phase with this name already exists for this project."})
            phase.name = name

        if sequence_order is not None:
            phase.sequence_order = int(sequence_order)
        if start_sprint_id is not None:
            phase.start_sprint_id = start_sprint_id or None
        if end_sprint_id is not None:
            phase.end_sprint_id = end_sprint_id or None
        if max_days_per_sprint is not None:
            from decimal import Decimal
            phase.max_days_per_sprint = Decimal(str(max_days_per_sprint)) if str(max_days_per_sprint).strip() else None
        if ramp_pattern is not None:
            phase.ramp_pattern = ramp_pattern
        if allow_multiple_engineers is not None:
            phase.allow_multiple_engineers = bool(allow_multiple_engineers)
        if split_mode is not None:
            phase.split_mode = split_mode
        if notes is not None:
            phase.notes = notes or None

        phase.save()
        return phase

    @staticmethod
    @transaction.atomic
    def delete_phase(phase):
        if PlanPhaseDependency.objects.filter(predecessor_phase=phase).exists():
            raise ValidationError({"detail": "Cannot delete: other phases depend on this phase."})
        phase.delete()

    # ── Segments ──────────────────────────────────────────────────────────────

    @staticmethod
    def list_segments(phase):
        return list(phase.segments.order_by("segment_order"))

    @staticmethod
    @transaction.atomic
    def add_segment(phase, segment_type, start_pct, end_pct, duration,
                    progression=None, step_count=None):
        from decimal import Decimal
        next_order = (phase.segments.order_by("-segment_order").values_list("segment_order", flat=True).first() or 0) + 1
        return PlanPhaseSegment.objects.create(
            phase=phase,
            segment_order=next_order,
            segment_type=segment_type,
            start_pct=Decimal(str(start_pct)),
            end_pct=Decimal(str(end_pct)),
            progression=progression or PlanPhaseSegment.PROG_LINEAR,
            duration=int(duration),
            step_count=int(step_count) if step_count is not None else None,
        )

    @staticmethod
    @transaction.atomic
    def update_segment(segment, segment_type=None, start_pct=None, end_pct=None,
                       duration=None, progression=None, step_count=None):
        from decimal import Decimal
        if segment_type is not None:
            segment.segment_type = segment_type
        if start_pct is not None:
            segment.start_pct = Decimal(str(start_pct))
        if end_pct is not None:
            segment.end_pct = Decimal(str(end_pct))
        if duration is not None:
            segment.duration = int(duration)
        if progression is not None:
            segment.progression = progression
        if step_count is not None:
            segment.step_count = int(step_count) if str(step_count).strip() else None
        segment.save()
        return segment

    @staticmethod
    @transaction.atomic
    def delete_segment(segment):
        segment.delete()

    @staticmethod
    def suggest_segments(phase):
        """Return a list of suggested segment dicts for the phase's ramp_pattern (does not save)."""
        pattern = phase.ramp_pattern
        suggestions = {
            PlanPhase.RAMP_FLAT: [
                {"segment_type": "FLAT", "start_pct": 100, "end_pct": 100, "progression": "FLAT", "duration": 1},
            ],
            PlanPhase.RAMP_UP: [
                {"segment_type": "RAMP", "start_pct": 0, "end_pct": 100, "progression": "LINEAR", "duration": 3},
                {"segment_type": "FLAT", "start_pct": 100, "end_pct": 100, "progression": "FLAT", "duration": 1},
            ],
            PlanPhase.RAMP_DOWN: [
                {"segment_type": "FLAT", "start_pct": 100, "end_pct": 100, "progression": "FLAT", "duration": 1},
                {"segment_type": "RAMP", "start_pct": 100, "end_pct": 0, "progression": "LINEAR", "duration": 3},
            ],
            PlanPhase.RAMP_UP_DOWN: [
                {"segment_type": "RAMP", "start_pct": 0, "end_pct": 100, "progression": "LINEAR", "duration": 2},
                {"segment_type": "RAMP", "start_pct": 100, "end_pct": 0, "progression": "LINEAR", "duration": 2},
            ],
            PlanPhase.RAMP_UP_STEADY: [
                {"segment_type": "RAMP", "start_pct": 0, "end_pct": 100, "progression": "LINEAR", "duration": 2},
                {"segment_type": "FLAT", "start_pct": 100, "end_pct": 100, "progression": "FLAT", "duration": 2},
            ],
            PlanPhase.STEADY_DOWN: [
                {"segment_type": "FLAT", "start_pct": 100, "end_pct": 100, "progression": "FLAT", "duration": 2},
                {"segment_type": "RAMP", "start_pct": 100, "end_pct": 0, "progression": "LINEAR", "duration": 2},
            ],
            PlanPhase.STEPPED: [
                {"segment_type": "RAMP", "start_pct": 0, "end_pct": 100, "progression": "STEPPED", "duration": 3, "step_count": 3},
            ],
        }
        result = suggestions.get(pattern, [])
        for i, seg in enumerate(result, 1):
            seg["segment_order"] = i
        return result

    @staticmethod
    @transaction.atomic
    def reorder_segments(phase, order_list):
        """order_list: list of segment ids in new order."""
        for i, seg_id in enumerate(order_list, 1):
            phase.segments.filter(pk=seg_id).update(segment_order=i)

    # ── Dependencies ──────────────────────────────────────────────────────────

    @staticmethod
    def list_dependencies(phase):
        return list(
            phase.dependencies.select_related(
                "predecessor_phase__plan_project_team__plan_project__project"
            ).order_by("id")
        )

    @staticmethod
    @transaction.atomic
    def add_dependency(phase, predecessor_id, dependency_type, lag_sprints=0):
        try:
            predecessor = PlanPhase.objects.select_related(
                "plan_project_team__plan_project__version"
            ).get(pk=predecessor_id)
        except PlanPhase.DoesNotExist:
            raise ValidationError({"predecessor_phase": "Predecessor phase not found."})

        if predecessor.pk == phase.pk:
            raise ValidationError({"predecessor_phase": "A phase cannot depend on itself."})

        # Ensure predecessor is in the same plan version
        phase_version = phase.plan_project_team.plan_project.version_id
        pred_version = predecessor.plan_project_team.plan_project.version_id
        if phase_version != pred_version:
            raise ValidationError({"predecessor_phase": "Predecessor must be in the same plan version."})

        if PlanPhaseDependency.objects.filter(phase=phase, predecessor_phase=predecessor).exists():
            raise ValidationError({"predecessor_phase": "This dependency already exists."})

        # BFS circular dependency check: starting from predecessor, can we reach `phase`?
        visited = set()
        queue = [predecessor.pk]
        while queue:
            current_pk = queue.pop()
            if current_pk == phase.pk:
                raise ValidationError({"predecessor_phase": "Adding this dependency would create a circular dependency."})
            if current_pk in visited:
                continue
            visited.add(current_pk)
            for dep in PlanPhaseDependency.objects.filter(phase_id=current_pk).values_list("predecessor_phase_id", flat=True):
                if dep not in visited:
                    queue.append(dep)

        return PlanPhaseDependency.objects.create(
            phase=phase,
            predecessor_phase=predecessor,
            dependency_type=dependency_type,
            lag_sprints=int(lag_sprints) if lag_sprints is not None else 0,
        )

    @staticmethod
    @transaction.atomic
    def update_dependency(dep, dependency_type=None, lag_sprints=None):
        if dependency_type is not None:
            dep.dependency_type = dependency_type
        if lag_sprints is not None:
            dep.lag_sprints = int(lag_sprints)
        dep.save()
        return dep

    @staticmethod
    @transaction.atomic
    def delete_dependency(dep):
        dep.delete()

    # ── Pauses ────────────────────────────────────────────────────────────────

    @staticmethod
    def list_pauses(phase):
        return list(
            phase.pauses.select_related("pause_from", "pause_until_sprint", "resume_sprint")
            .order_by("pause_from__sprint_number")
        )

    @staticmethod
    @transaction.atomic
    def add_pause(phase, pause_from_id, input_mode, pause_until_sprint_id=None, pause_sprint_count=None, notes=None):
        from apps.sprints.models import Sprint

        try:
            pause_from = Sprint.objects.get(pk=pause_from_id)
        except Sprint.DoesNotExist:
            raise ValidationError({"pause_from": "Sprint not found."})

        # Overlap check
        if phase.pauses.filter(pause_from=pause_from).exists():
            raise ValidationError({"pause_from": "A pause starting from this sprint already exists."})

        pause_until = None
        if input_mode == PlanPhasePause.INPUT_SPRINT:
            if not pause_until_sprint_id:
                raise ValidationError({"pause_until_sprint": "Pause until sprint is required."})
            try:
                pause_until = Sprint.objects.get(pk=pause_until_sprint_id)
            except Sprint.DoesNotExist:
                raise ValidationError({"pause_until_sprint": "Sprint not found."})
            if pause_until.sprint_number <= pause_from.sprint_number:
                raise ValidationError({"pause_until_sprint": "Pause until sprint must be after pause from sprint."})
        elif input_mode == PlanPhasePause.INPUT_COUNT:
            if not pause_sprint_count or int(pause_sprint_count) < 1:
                raise ValidationError({"pause_sprint_count": "Sprint count must be at least 1."})

        # Resolve resume_sprint and is_beyond_fy
        resume_sprint, is_beyond_fy = PlanPhaseService._resolve_resume_sprint(
            phase, pause_from, input_mode, pause_until, pause_sprint_count
        )

        return PlanPhasePause.objects.create(
            phase=phase,
            pause_from=pause_from,
            input_mode=input_mode,
            pause_until_sprint=pause_until,
            pause_sprint_count=int(pause_sprint_count) if pause_sprint_count else None,
            resume_sprint=resume_sprint,
            is_beyond_fy=is_beyond_fy,
            notes=notes or None,
        )

    @staticmethod
    @transaction.atomic
    def update_pause(pause, input_mode=None, pause_until_sprint_id=None,
                     pause_sprint_count=None, notes=None):
        from apps.sprints.models import Sprint

        if input_mode is not None:
            pause.input_mode = input_mode

        if pause.input_mode == PlanPhasePause.INPUT_SPRINT and pause_until_sprint_id is not None:
            try:
                pause_until = Sprint.objects.get(pk=pause_until_sprint_id)
            except Sprint.DoesNotExist:
                raise ValidationError({"pause_until_sprint": "Sprint not found."})
            pause.pause_until_sprint = pause_until
            pause.pause_sprint_count = None
        elif pause.input_mode == PlanPhasePause.INPUT_COUNT and pause_sprint_count is not None:
            pause.pause_sprint_count = int(pause_sprint_count)
            pause.pause_until_sprint = None

        resume_sprint, is_beyond_fy = PlanPhaseService._resolve_resume_sprint(
            pause.phase, pause.pause_from, pause.input_mode,
            pause.pause_until_sprint, pause.pause_sprint_count
        )
        pause.resume_sprint = resume_sprint
        pause.is_beyond_fy = is_beyond_fy

        if notes is not None:
            pause.notes = notes or None

        pause.save()
        return pause

    @staticmethod
    @transaction.atomic
    def delete_pause(pause):
        pause.delete()

    @staticmethod
    def _resolve_resume_sprint(phase, pause_from, input_mode, pause_until, pause_sprint_count):
        """Calculate resume sprint. Returns (sprint_obj_or_None, is_beyond_fy)."""
        from apps.sprints.models import Sprint

        fy_id = (
            ResourcePlanScope.objects.filter(
                plan_group=phase.plan_project_team.plan_project.version.plan_group
            ).values_list("financial_year_id", flat=True).first()
        )

        if input_mode == PlanPhasePause.INPUT_SPRINT and pause_until:
            # Resume is the sprint after pause_until
            resume = Sprint.objects.filter(
                financial_year_id=fy_id,
                sprint_number__gt=pause_until.sprint_number,
            ).order_by("sprint_number").first()
            is_beyond_fy = resume is None
            return resume, is_beyond_fy

        elif input_mode == PlanPhasePause.INPUT_COUNT and pause_sprint_count:
            count = int(pause_sprint_count)
            resume = Sprint.objects.filter(
                financial_year_id=fy_id,
                sprint_number__gt=pause_from.sprint_number + count - 1,
            ).order_by("sprint_number").first()
            is_beyond_fy = resume is None
            return resume, is_beyond_fy

        return None, False

    @staticmethod
    def get_phases_options(version):
        """Return phases grouped by project for the dependency predecessor selector."""
        phases = PlanPhase.objects.filter(
            plan_project_team__plan_project__version=version
        ).select_related(
            "plan_project_team__plan_project__project",
            "plan_project_team__team",
        ).order_by(
            "plan_project_team__plan_project__project__name",
            "plan_project_team__team__name",
            "sequence_order",
        )

        groups = {}
        for ph in phases:
            project = ph.plan_project_team.plan_project.project
            team = ph.plan_project_team.team
            key = project.id
            if key not in groups:
                groups[key] = {"project_id": project.id, "project_name": project.name, "phases": []}
            groups[key]["phases"].append({
                "id": ph.id,
                "name": ph.name,
                "team_name": team.name,
                "sequence_order": ph.sequence_order,
            })
        return list(groups.values())


# ── Assignment helpers ─────────────────────────────────────────────────────────

def _recompute_split_incomplete(phase):
    """Recompute PlanPhase.is_split_incomplete based on current PERCENT assignments."""
    from decimal import Decimal
    if phase.split_mode == PlanPhase.SPLIT_PERCENT:
        total = phase.assignments.filter(
            split_value__isnull=False
        ).aggregate(s=models.Sum("split_value"))["s"] or Decimal("0")
        phase.is_split_incomplete = abs(total - Decimal("100")) > Decimal("0.01")
    else:
        phase.is_split_incomplete = False
    phase.save(update_fields=["is_split_incomplete"])


class PlanAssignmentService:

    @staticmethod
    def list_assignments(phase):
        return list(
            phase.assignments.select_related("team_member", "replaces_member").order_by("id")
        )

    @staticmethod
    def get_assignment(pk):
        return PlanAssignment.objects.select_related(
            "phase__plan_project_team", "team_member", "replaces_member"
        ).get(pk=pk)

    @staticmethod
    def get_assignment_options(phase):
        """Available team members for assignment (team members from the phase's delivery team only)."""
        from apps.team_members.models import TeamMember
        team = phase.plan_project_team.team if phase.plan_project_team else None
        assigned_ids = phase.assignments.exclude(
            team_member__isnull=True
        ).values_list("team_member_id", flat=True)
        if team:
            team_members = TeamMember.objects.filter(team=team, is_active=True).order_by("last_name", "first_name")
        else:
            team_members = TeamMember.objects.none()
        available = team_members.exclude(id__in=assigned_ids)
        return {
            "available": [{"id": m.id, "name": m.display_name} for m in available],
            "all": [{"id": m.id, "name": m.display_name} for m in team_members],
            "split_mode": phase.split_mode,
            "allow_multiple": phase.allow_multiple_engineers,
        }

    @staticmethod
    @transaction.atomic
    def create_assignment(phase, team_member_id=None, auto_assign=False,
                          assignment_type=None, replaces_member_id=None,
                          interim_sprint_count=None, split_value=None, notes=None):
        from apps.team_members.models import TeamMember
        from decimal import Decimal

        assignment_type = assignment_type or PlanAssignment.ASSIGN_ENGINEER

        if not auto_assign and not team_member_id:
            raise ValidationError({"team_member": "Select an engineer or enable auto-assign."})

        team_member = None
        if team_member_id:
            try:
                team_member = TeamMember.objects.get(pk=team_member_id)
            except TeamMember.DoesNotExist:
                raise ValidationError({"team_member": "Team member not found."})

        # Duplicate check
        if not auto_assign and team_member:
            if PlanAssignment.objects.filter(phase=phase, team_member=team_member).exists():
                raise ValidationError({"team_member": "This engineer is already assigned to this phase."})

        # Multiple-engineer guard
        if not phase.allow_multiple_engineers and phase.assignments.exists():
            raise ValidationError({"phase": "This phase does not allow multiple assignments. Enable 'Allow Multiple Engineers' on the phase first."})

        replaces_member = None
        if assignment_type == PlanAssignment.ASSIGN_INTERIM:
            if not replaces_member_id:
                raise ValidationError({"replaces_member": "INTERIM assignment must specify who it replaces."})
            if not interim_sprint_count or int(interim_sprint_count) < 1:
                raise ValidationError({"interim_sprint_count": "INTERIM assignment must specify a sprint count ≥ 1."})
            try:
                replaces_member = TeamMember.objects.get(pk=replaces_member_id)
            except TeamMember.DoesNotExist:
                raise ValidationError({"replaces_member": "Team member not found."})

        includes_in_budget = (assignment_type == PlanAssignment.ASSIGN_ENGINEER)

        split_val = None
        if split_value is not None and phase.split_mode in (PlanPhase.SPLIT_PERCENT, PlanPhase.SPLIT_DAYS):
            split_val = Decimal(str(split_value))

        assignment = PlanAssignment.objects.create(
            phase=phase,
            team_member=team_member,
            auto_assign=bool(auto_assign),
            assignment_type=assignment_type,
            replaces_member=replaces_member,
            interim_sprint_count=int(interim_sprint_count) if interim_sprint_count else None,
            split_value=split_val,
            includes_in_budget=includes_in_budget,
            notes=notes or None,
        )
        _recompute_split_incomplete(phase)
        return assignment

    @staticmethod
    @transaction.atomic
    def update_assignment(assignment, assignment_type=None, team_member_id=None,
                          auto_assign=None, replaces_member_id=None,
                          interim_sprint_count=None, split_value=None, notes=None):
        from apps.team_members.models import TeamMember
        from decimal import Decimal

        phase = assignment.phase

        if auto_assign is not None:
            assignment.auto_assign = bool(auto_assign)
            if assignment.auto_assign:
                assignment.team_member = None

        if not assignment.auto_assign and team_member_id is not None:
            try:
                tm = TeamMember.objects.get(pk=team_member_id)
            except TeamMember.DoesNotExist:
                raise ValidationError({"team_member": "Team member not found."})
            if PlanAssignment.objects.filter(
                phase=phase, team_member=tm
            ).exclude(pk=assignment.pk).exists():
                raise ValidationError({"team_member": "This engineer is already assigned to this phase."})
            assignment.team_member = tm

        if assignment_type is not None:
            assignment.assignment_type = assignment_type
            assignment.includes_in_budget = (assignment_type == PlanAssignment.ASSIGN_ENGINEER)

        if assignment.assignment_type == PlanAssignment.ASSIGN_INTERIM:
            if replaces_member_id is not None:
                try:
                    assignment.replaces_member = TeamMember.objects.get(pk=replaces_member_id)
                except TeamMember.DoesNotExist:
                    raise ValidationError({"replaces_member": "Team member not found."})
            if interim_sprint_count is not None:
                assignment.interim_sprint_count = int(interim_sprint_count)
        else:
            assignment.replaces_member = None
            assignment.interim_sprint_count = None

        if split_value is not None and phase.split_mode in (PlanPhase.SPLIT_PERCENT, PlanPhase.SPLIT_DAYS):
            assignment.split_value = Decimal(str(split_value))
        elif phase.split_mode not in (PlanPhase.SPLIT_PERCENT, PlanPhase.SPLIT_DAYS):
            assignment.split_value = None

        if notes is not None:
            assignment.notes = notes or None

        assignment.save()
        _recompute_split_incomplete(phase)
        return assignment

    @staticmethod
    @transaction.atomic
    def delete_assignment(assignment):
        phase = assignment.phase
        assignment.delete()
        _recompute_split_incomplete(phase)


# ── Version configuration deep copy ───────────────────────────────────────────

def _deep_copy_version_config(source_version, target_version):
    """
    Copy all Projects / Teams / Phases / Segments / Pauses / Assignments /
    BudgetReleases from source_version into target_version.
    Phase dependencies are remapped to the new phase IDs.
    """
    phase_id_map = {}  # old id → new phase object

    for src_proj in (
        ResourcePlanVersionProject.objects.filter(version=source_version)
        .prefetch_related(
            "teams__phases__segments",
            "teams__phases__pauses",
            "teams__phases__assignments",
            "teams__phases__dependencies",
            "budget_releases",
        )
    ):
        new_proj = ResourcePlanVersionProject.objects.create(
            version=target_version,
            project=src_proj.project,
            basis=src_proj.basis,
            basis_amount=src_proj.basis_amount,
            basis_synced_at=src_proj.basis_synced_at,
            snapshotted_budget=src_proj.snapshotted_budget,
            snapshotted_estimate=src_proj.snapshotted_estimate,
            days_required=src_proj.days_required,
            is_over_threshold=src_proj.is_over_threshold,
            is_under_threshold=src_proj.is_under_threshold,
            is_team_budget_mismatch=src_proj.is_team_budget_mismatch,
            is_percent_incomplete=src_proj.is_percent_incomplete,
            priority_snapshot=src_proj.priority_snapshot,
            priority_override=src_proj.priority_override,
            confidence_snapshot=src_proj.confidence_snapshot,
            confidence_override=src_proj.confidence_override,
            start_sprint=src_proj.start_sprint,
            end_sprint=src_proj.end_sprint,
            dates_strict=src_proj.dates_strict,
            budget_release_mode=src_proj.budget_release_mode,
            display_order=src_proj.display_order,
        )

        for rel in src_proj.budget_releases.all():
            ResourcePlanVersionProjectBudgetRelease.objects.create(
                plan_project=new_proj,
                entry_type=rel.entry_type,
                sprint=rel.sprint,
                month=rel.month,
                amount=rel.amount,
                notes=rel.notes,
            )

        for src_team in src_proj.teams.all():
            new_team = ResourcePlanVersionProjectTeam.objects.create(
                plan_project=new_proj,
                team=src_team.team,
                allocation_type=src_team.allocation_type,
                allocation_pct=src_team.allocation_pct,
                allocation_days=src_team.allocation_days,
                allocation_budget=src_team.allocation_budget,
                allocated_days=src_team.allocated_days,
                sequence_order=src_team.sequence_order,
            )

            for src_phase in src_team.phases.all():
                new_phase = PlanPhase.objects.create(
                    plan_project_team=new_team,
                    name=src_phase.name,
                    sequence_order=src_phase.sequence_order,
                    start_sprint=src_phase.start_sprint,
                    end_sprint=src_phase.end_sprint,
                    max_days_per_sprint=src_phase.max_days_per_sprint,
                    ramp_pattern=src_phase.ramp_pattern,
                    allow_multiple_engineers=src_phase.allow_multiple_engineers,
                    split_mode=src_phase.split_mode,
                    is_split_incomplete=src_phase.is_split_incomplete,
                    notes=src_phase.notes,
                )
                phase_id_map[src_phase.id] = new_phase

                for seg in src_phase.segments.all():
                    PlanPhaseSegment.objects.create(
                        phase=new_phase,
                        segment_order=seg.segment_order,
                        segment_type=seg.segment_type,
                        start_pct=seg.start_pct,
                        end_pct=seg.end_pct,
                        progression=seg.progression,
                        duration=seg.duration,
                        step_count=seg.step_count,
                    )

                for pause in src_phase.pauses.all():
                    PlanPhasePause.objects.create(
                        phase=new_phase,
                        pause_from=pause.pause_from,
                        input_mode=pause.input_mode,
                        pause_until_sprint=pause.pause_until_sprint,
                        pause_sprint_count=pause.pause_sprint_count,
                        resume_sprint=pause.resume_sprint,
                        is_beyond_fy=pause.is_beyond_fy,
                        notes=pause.notes,
                    )

                for asgn in src_phase.assignments.all():
                    PlanAssignment.objects.create(
                        phase=new_phase,
                        team_member=asgn.team_member,
                        auto_assign=asgn.auto_assign,
                        assignment_type=asgn.assignment_type,
                        replaces_member=asgn.replaces_member,
                        interim_sprint_count=asgn.interim_sprint_count,
                        split_value=asgn.split_value,
                        includes_in_budget=asgn.includes_in_budget,
                        notes=asgn.notes,
                    )

    # Remap dependencies (requires all new phases to exist first)
    for old_id, new_phase in phase_id_map.items():
        src_phase = PlanPhase.objects.get(pk=old_id)
        for dep in src_phase.dependencies.all():
            new_pred = phase_id_map.get(dep.predecessor_phase_id)
            if new_pred:
                PlanPhaseDependency.objects.get_or_create(
                    phase=new_phase,
                    predecessor_phase=new_pred,
                    defaults={
                        "dependency_type": dep.dependency_type,
                        "lag_sprints": dep.lag_sprints,
                    },
                )


# ── Engine Job (logic lives in engine.py) ──────────────────────────────────────


class PlaceholderLeaveService:

    @staticmethod
    def generate_for_version(version, include_current_sprint=False, remove_overrides=False):
        """
        Generate PlaceholderLeave records for all directly-assigned members in a version.
        Clears auto-generated records first; preserves manual overrides (is_auto=False).

        Distribution: remaining entitlement days spread across second-half FY sprints,
        each sprint capped at its available SprintCapacity net. If <= FORCE_WINDOW future
        sprints remain, only those sprints receive distribution.
        """
        from apps.sprint_capacity.models import SprintCapacity
        from apps.member_leaves.models import LeaveDay
        from apps.configurations.services import ConfigurationService
        from apps.sprints.models import Sprint

        force_window = ConfigurationService.get_int('RESOURCE_PLAN_PLACEHOLDER_FORCE_WINDOW', fallback=3)
        default_holidays = ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        if not scope:
            return

        fy = scope.financial_year
        all_sprints = list(Sprint.objects.filter(financial_year=fy).order_by('sprint_number'))
        if not all_sprints:
            return

        mid = len(all_sprints) // 2
        second_half = all_sprints[mid:]
        today = timezone.now().date()

        if include_current_sprint:
            future_sprints = [s for s in second_half if s.end_date >= today]
        else:
            future_sprints = [s for s in second_half if s.start_date > today]

        if not future_sprints:
            return

        if len(future_sprints) <= force_window:
            target_sprints = future_sprints
        else:
            target_sprints = future_sprints

        dt_ids = list(
            ResourcePlanVersionProjectTeam.objects.filter(plan_project__version=version)
            .values_list('team_id', flat=True).distinct()
        )
        from apps.team_members.models import TeamMember
        members = list(TeamMember.objects.filter(team_id__in=dt_ids, is_active=True).select_related('location'))
        if not members:
            return
        member_ids = [m.id for m in members]

        fy_start = fy.start_date
        fy_end = fy.end_date

        if remove_overrides:
            PlaceholderLeave.objects.filter(version=version).delete()
        else:
            PlaceholderLeave.objects.filter(
                version=version, team_member_id__in=member_ids, is_auto=True
            ).delete()

        sprint_ids = [s.id for s in target_sprints]
        cap_map = {}
        for sc in SprintCapacity.objects.filter(sprint_id__in=sprint_ids, team_member_id__in=member_ids):
            cap_map[(sc.team_member_id, sc.sprint_id)] = max(
                Decimal('0'), sc.working_days - sc.holiday_days - sc.leave_days
            )

        to_create = []
        for member in members:
            entitlement = Decimal(str(member.default_holidays or default_holidays))

            leave_days_qs = LeaveDay.objects.filter(
                member=member, date__gte=fy_start, date__lte=fy_end
            )
            past_leave = Decimal('0')
            future_leave = Decimal('0')
            for ld in leave_days_qs:
                increment = Decimal('0.5') if ld.is_half_day else Decimal('1')
                if ld.date < today:
                    past_leave += increment
                else:
                    future_leave += increment

            remaining = entitlement - past_leave - future_leave
            if remaining <= 0:
                continue

            n = len(target_sprints)
            per_sprint = remaining / n
            allocs = []
            leftover = remaining
            for sprint in target_sprints:
                cap = cap_map.get((member.id, sprint.id), Decimal('10'))
                alloc = min(per_sprint, cap, leftover)
                alloc = max(Decimal('0'), (alloc * 2).quantize(Decimal('1')) / 2)
                allocs.append([sprint, alloc])
                leftover -= alloc

            if leftover > 0:
                for pair in allocs:
                    if leftover <= 0:
                        break
                    sprint = pair[0]
                    cap = cap_map.get((member.id, sprint.id), Decimal('10'))
                    extra = min(leftover, cap - pair[1])
                    if extra > 0:
                        pair[1] += extra
                        leftover -= extra

            for sprint, alloc in allocs:
                if alloc > 0:
                    to_create.append(PlaceholderLeave(
                        version=version, team_member=member, sprint=sprint,
                        days=alloc, is_auto=True,
                    ))

        PlaceholderLeave.objects.bulk_create(to_create, ignore_conflicts=True)

    @staticmethod
    def list_for_version(version, team_member_id=None, team_id=None):
        qs = PlaceholderLeave.objects.filter(version=version).select_related('team_member', 'sprint')
        if team_member_id:
            qs = qs.filter(team_member_id=team_member_id)
        if team_id:
            qs = qs.filter(team_member__team_id=team_id)
        return qs.order_by('sprint__sprint_number', 'team_member__last_name', 'team_member__first_name')

    @staticmethod
    def update_placeholder(placeholder_leave, days, notes=None):
        placeholder_leave.days = Decimal(str(days))
        placeholder_leave.is_auto = False
        if notes is not None:
            placeholder_leave.notes = notes or None
        placeholder_leave.save()
        return placeholder_leave

    @staticmethod
    def delete_placeholder(placeholder_leave):
        placeholder_leave.delete()


class CapacityService:

    @staticmethod
    def get_team_tabs(version):
        """Return unique delivery teams that have assignments in this version."""
        team_entries = (
            ResourcePlanVersionProjectTeam.objects.filter(
                plan_project__version=version
            ).select_related('team').order_by('team__name')
        )
        seen = {}
        result = []
        for te in team_entries:
            if te.team_id not in seen:
                seen[te.team_id] = True
                result.append({'id': te.team.id, 'name': te.team.name})
        return result

    @staticmethod
    def _get_members_for_version(version, team_id=None):
        from apps.team_members.models import TeamMember
        team_qs = ResourcePlanVersionProjectTeam.objects.filter(plan_project__version=version)
        if team_id:
            team_qs = team_qs.filter(team_id=team_id)
        dt_ids = list(team_qs.values_list('team_id', flat=True).distinct())

        members = list(
            TeamMember.objects.filter(team_id__in=dt_ids, is_active=True)
            .order_by('last_name', 'first_name')
        )
        return {m.id: m for m in members}

    @staticmethod
    def get_capacity_grid(version, team_id=None):
        """Table 1: net capacity per member per sprint from the plan snapshot."""
        from apps.sprints.models import Sprint
        from .models import ResourcePlanMemberCapacity

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        sprint_list = (
            list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))
            if scope else []
        )
        sprint_meta = [{'id': s.id, 'name': s.sprint_name, 'month': s.month} for s in sprint_list]

        member_map = CapacityService._get_members_for_version(version, team_id)
        if not member_map:
            return {'sprints': sprint_meta, 'rows': []}

        # Auto-populate snapshot if this version has never been synced
        if not ResourcePlanMemberCapacity.objects.filter(version=version).exists():
            CapacitySnapshotService.sync_for_version(version)

        sprint_ids = [s.id for s in sprint_list]
        snap_lookup = {
            (rc.team_member_id, rc.sprint_id): rc
            for rc in ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id__in=member_map.keys(), sprint_id__in=sprint_ids
            )
        }

        rows = []
        for member_id, member in sorted(member_map.items(), key=lambda x: (x[1].last_name, x[1].first_name)):
            cells = []
            for sprint in sprint_list:
                rc = snap_lookup.get((member_id, sprint.id))
                if rc:
                    cells.append({
                        'sprint_id': sprint.id,
                        'working_days': str(rc.working_days),
                        'holiday_days': str(rc.holiday_days),
                        'leave_days': str(rc.leave_days),
                        'placeholder_days': str(rc.placeholder_days),
                        'net_capacity': str(rc.net_capacity),
                    })
                else:
                    cells.append({
                        'sprint_id': sprint.id,
                        'working_days': None,
                        'holiday_days': None,
                        'leave_days': None,
                        'placeholder_days': '0',
                        'net_capacity': None,
                    })
            rows.append({'member_id': member_id, 'member_name': member.display_name, 'cells': cells})

        return {'sprints': sprint_meta, 'rows': rows}

    @staticmethod
    def get_absences_grid(version, team_id=None):
        """Table 2: absence breakdown per member per sprint from the plan snapshot."""
        from apps.sprints.models import Sprint
        from .models import ResourcePlanMemberCapacity

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        sprint_list = (
            list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))
            if scope else []
        )
        sprint_meta = [{'id': s.id, 'name': s.sprint_name, 'month': s.month} for s in sprint_list]

        member_map = CapacityService._get_members_for_version(version, team_id)
        if not member_map:
            return {'sprints': sprint_meta, 'rows': []}

        # Auto-populate snapshot if this version has never been synced
        if not ResourcePlanMemberCapacity.objects.filter(version=version).exists():
            CapacitySnapshotService.sync_for_version(version)

        sprint_ids = [s.id for s in sprint_list]
        snap_lookup = {
            (rc.team_member_id, rc.sprint_id): rc
            for rc in ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id__in=member_map.keys(), sprint_id__in=sprint_ids
            )
        }

        rows = []
        for member_id, member in sorted(member_map.items(), key=lambda x: (x[1].last_name, x[1].first_name)):
            cells = []
            for sprint in sprint_list:
                rc = snap_lookup.get((member_id, sprint.id))
                if rc:
                    total = rc.holiday_days + rc.leave_days + rc.placeholder_days
                    cells.append({
                        'sprint_id': sprint.id,
                        'holiday_days': str(rc.holiday_days),
                        'leave_days': str(rc.leave_days),
                        'placeholder_days': str(rc.placeholder_days),
                        'total_absence': str(total),
                    })
                else:
                    cells.append({
                        'sprint_id': sprint.id,
                        'holiday_days': None,
                        'leave_days': None,
                        'placeholder_days': '0',
                        'total_absence': None,
                    })
            rows.append({'member_id': member_id, 'member_name': member.display_name, 'cells': cells})

        return {'sprints': sprint_meta, 'rows': rows}


class CapacitySnapshotService:
    """Materialises SprintCapacity + PlaceholderLeave into ResourcePlanMemberCapacity."""

    @staticmethod
    def sync_for_version(version):
        from apps.sprint_capacity.models import SprintCapacity
        from apps.sprints.models import Sprint
        from .models import ResourcePlanMemberCapacity

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        if not scope:
            return

        sprint_list = list(
            Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number')
        )
        sprint_ids = [s.id for s in sprint_list]

        member_map = CapacityService._get_members_for_version(version)
        if not member_map:
            ResourcePlanMemberCapacity.objects.filter(version=version).delete()
            return

        member_ids = list(member_map.keys())

        cap_lookup = {
            (sc.team_member_id, sc.sprint_id): sc
            for sc in SprintCapacity.objects.filter(
                sprint_id__in=sprint_ids, team_member_id__in=member_ids
            )
        }
        pl_lookup = {
            (pl.team_member_id, pl.sprint_id): pl.days
            for pl in PlaceholderLeave.objects.filter(
                version=version, team_member_id__in=member_ids, sprint_id__in=sprint_ids
            )
        }

        to_create = []
        for member_id in member_ids:
            for sprint in sprint_list:
                sc = cap_lookup.get((member_id, sprint.id))
                ph = pl_lookup.get((member_id, sprint.id), Decimal('0'))
                if sc:
                    net = max(Decimal('0'), sc.net_capacity - ph)
                    to_create.append(ResourcePlanMemberCapacity(
                        version=version,
                        team_member_id=member_id,
                        sprint_id=sprint.id,
                        working_days=sc.working_days,
                        holiday_days=sc.holiday_days,
                        leave_days=sc.leave_days,
                        placeholder_days=ph,
                        net_capacity=net,
                    ))
                elif ph > 0:
                    to_create.append(ResourcePlanMemberCapacity(
                        version=version,
                        team_member_id=member_id,
                        sprint_id=sprint.id,
                        working_days=Decimal('0'),
                        holiday_days=Decimal('0'),
                        leave_days=Decimal('0'),
                        placeholder_days=ph,
                        net_capacity=Decimal('0'),
                    ))

        ResourcePlanMemberCapacity.objects.filter(version=version).delete()
        if to_create:
            ResourcePlanMemberCapacity.objects.bulk_create(to_create)

    @staticmethod
    def sync_record(version, team_member_id, sprint_id):
        """Lightweight single-record resync after a PL is edited or deleted."""
        from apps.sprint_capacity.models import SprintCapacity
        from .models import ResourcePlanMemberCapacity

        try:
            sc = SprintCapacity.objects.get(team_member_id=team_member_id, sprint_id=sprint_id)
        except SprintCapacity.DoesNotExist:
            ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id=team_member_id, sprint_id=sprint_id
            ).delete()
            return

        ph_qs = PlaceholderLeave.objects.filter(
            version=version, team_member_id=team_member_id, sprint_id=sprint_id
        ).values_list('days', flat=True).first()
        ph = Decimal(str(ph_qs)) if ph_qs is not None else Decimal('0')
        net = max(Decimal('0'), sc.net_capacity - ph)

        ResourcePlanMemberCapacity.objects.update_or_create(
            version=version,
            team_member_id=team_member_id,
            sprint_id=sprint_id,
            defaults={
                'working_days': sc.working_days,
                'holiday_days': sc.holiday_days,
                'leave_days': sc.leave_days,
                'placeholder_days': ph,
                'net_capacity': net,
            },
        )


class PlanEngineJobService:

    @staticmethod
    def get_running_job(plan):
        return PlanEngineJob.objects.filter(
            plan=plan,
            status__in=[PlanEngineJob.STATUS_PENDING, PlanEngineJob.STATUS_RUNNING],
        ).first()

    @staticmethod
    def list_jobs(plan, mode=None, version_id=None):
        qs = PlanEngineJob.objects.filter(plan=plan).select_related("version")
        if mode in (PlanEngineJob.MODE_VALIDATE, PlanEngineJob.MODE_FULL):
            qs = qs.filter(mode=mode)
        if version_id:
            qs = qs.filter(version_id=version_id)
        return qs

    @staticmethod
    def get_job(job_id):
        return PlanEngineJob.objects.select_related("plan", "version").get(pk=job_id)

    @staticmethod
    def create_job(plan, version, mode=PlanEngineJob.MODE_VALIDATE,
                   include_current_sprint=False, dry_run=False, remove_overrides=False):
        from .engine import run_engine
        running = PlanEngineJobService.get_running_job(plan)
        if running:
            raise ValidationError(
                {"running_job_id": running.pk, "detail": "A job is already running for this plan."}
            )
        job = PlanEngineJob.objects.create(
            plan=plan,
            version=version,
            mode=mode,
            include_current_sprint=include_current_sprint,
            dry_run=dry_run,
            remove_overrides=remove_overrides,
        )
        t = threading.Thread(target=run_engine, args=(job.pk,), daemon=True)
        t.start()
        return job
