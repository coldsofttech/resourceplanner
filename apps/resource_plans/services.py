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

    # Copy manual PlaceholderLeave overrides (is_auto=False) so that manual edits survive cloning
    pl_to_copy = PlaceholderLeave.objects.filter(version=source_version, is_auto=False)
    if pl_to_copy.exists():
        PlaceholderLeave.objects.bulk_create([
            PlaceholderLeave(
                version=target_version,
                team_member=pl.team_member,
                sprint=pl.sprint,
                days=pl.days,
                is_auto=False,
                notes=pl.notes,
            )
            for pl in pl_to_copy
        ], ignore_conflicts=True)
        ResourcePlanVersion.objects.filter(pk=target_version.pk).update(has_pl_overrides=True)


# ── Engine Job (logic lives in engine.py) ──────────────────────────────────────


class PlaceholderLeaveService:

    @staticmethod
    def clear_overrides_for_version(version):
        """Delete all placeholder leaves for version, including manual overrides."""
        PlaceholderLeave.objects.filter(version=version).delete()

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
            .select_related('team')
            .order_by('last_name', 'first_name')
        )
        return {
            m.id: {
                'member': m,
                'team_id': m.team_id,
                'team_name': m.team.name if m.team_id else '',
            }
            for m in members
        }

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
        for member_id, minfo in sorted(member_map.items(), key=lambda x: (x[1]['member'].last_name, x[1]['member'].first_name)):
            member = minfo['member']
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
            rows.append({
                'member_id': member_id,
                'member_name': member.display_name,
                'team_id': minfo['team_id'],
                'team_name': minfo['team_name'],
                'cells': cells,
            })

        rows += PlaceholderEngineerService.get_placeholder_capacity(version, team_id)
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
        for member_id, minfo in sorted(member_map.items(), key=lambda x: (x[1]['member'].last_name, x[1]['member'].first_name)):
            member = minfo['member']
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
            rows.append({
                'member_id': member_id,
                'member_name': member.display_name,
                'team_id': minfo['team_id'],
                'team_name': minfo['team_name'],
                'cells': cells,
            })

        rows += PlaceholderEngineerService.get_placeholder_absences(version, team_id)
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


# ── Phase 7: Allocation Engine Services ───────────────────────────────────────


class RampDistributionService:
    """Pure computation — no DB access. Distributes total_days across sprint_count slots."""

    @staticmethod
    def distribute(total_days, sprint_count, ramp_pattern='FLAT', segments=None, max_days_per_sprint=None):
        if sprint_count <= 0 or not total_days:
            return []
        from decimal import Decimal as D, ROUND_HALF_UP
        total = D(str(total_days))
        weights = RampDistributionService._compute_weights(sprint_count, ramp_pattern, segments)
        w_sum = sum(weights) or 1.0
        normalised = [w / w_sum for w in weights]
        raw = [total * D(str(n)) for n in normalised]

        if max_days_per_sprint is not None:
            cap = D(str(max_days_per_sprint))
            capped = [min(d, cap) for d in raw]
            excess = sum(r - c for r, c in zip(raw, capped))
            raw = capped
            if excess > 0:
                for i, d in enumerate(raw):
                    if excess <= 0:
                        break
                    if d < cap:
                        add = min(excess, cap - d)
                        raw[i] += add
                        excess -= add

        QUARTER = D('0.25')
        rounded = [(d / QUARTER).quantize(D('1'), rounding=ROUND_HALF_UP) * QUARTER for d in raw]
        return rounded

    @staticmethod
    def _compute_weights(n, ramp_pattern, segments):
        if segments:
            return RampDistributionService._weights_from_segments(n, segments)
        patterns = {
            'FLAT':         lambda n: [1.0] * n,
            'RAMP_UP':      lambda n: [float(i + 1) for i in range(n)],
            'RAMP_DOWN':    lambda n: [float(n - i) for i in range(n)],
            'RAMP_UP_DOWN': RampDistributionService._ramp_up_down,
            'RAMP_UP_STEADY': RampDistributionService._ramp_up_steady,
            'STEADY_DOWN':  RampDistributionService._steady_down,
            'STEPPED':      RampDistributionService._stepped,
        }
        fn = patterns.get(ramp_pattern, patterns['FLAT'])
        return fn(n)

    @staticmethod
    def _ramp_up_down(n):
        mid = max(1, n // 2)
        up = [float(i + 1) for i in range(mid)]
        down = [float(n - mid - i) for i in range(n - mid)]
        return up + down

    @staticmethod
    def _ramp_up_steady(n):
        ramp = max(1, n // 3)
        peak = float(ramp)
        return [float(i + 1) for i in range(ramp)] + [peak] * (n - ramp)

    @staticmethod
    def _steady_down(n):
        steady = max(1, (2 * n) // 3)
        drop = n - steady
        peak = float(drop + 1) if drop else 1.0
        return [peak] * steady + [float(drop - i) for i in range(drop)]

    @staticmethod
    def _stepped(n, steps=3):
        return [float(int(i / (n / steps)) + 1) for i in range(n)]

    @staticmethod
    def _weights_from_segments(n, segments):
        import math
        total_dur = sum(s.duration for s in segments) or 1
        weights = []
        for i in range(n):
            pos = (i / n) * total_dur
            cursor = 0
            w = 0.01
            for seg in segments:
                seg_end = cursor + seg.duration
                if pos < seg_end or seg == segments[-1]:
                    t = (pos - cursor) / seg.duration if seg.duration else 0.0
                    t = max(0.0, min(1.0, t))
                    s0 = float(seg.start_pct) / 100.0
                    s1 = float(seg.end_pct) / 100.0
                    prog = seg.progression
                    if seg.segment_type == 'FLAT':
                        w = (s0 + s1) / 2.0
                    elif prog == 'LINEAR':
                        w = s0 + (s1 - s0) * t
                    elif prog == 'EXPONENTIAL':
                        w = s0 + (s1 - s0) * (t ** 2)
                    elif prog == 'LOGARITHMIC':
                        w = s0 + (s1 - s0) * (math.log1p(t * (math.e - 1)))
                    elif prog == 'STEPPED':
                        steps = seg.step_count or 3
                        w = s0 + (s1 - s0) * (int(t * steps) / steps)
                    else:
                        w = (s0 + s1) / 2.0
                    break
                cursor = seg_end
            weights.append(max(0.001, w))
        return weights


class DependencyGraphService:
    PRIORITY_RANK = {'VERY_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    CONFIDENCE_RANK = {'VERY_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}

    @staticmethod
    def topological_sort(phases, proj_by_phase_id):
        """Kahn's algorithm with priority-based tie-breaking."""
        if not phases:
            return []
        import heapq
        phase_ids = {ph.id for ph in phases}
        in_deg = {ph.id: 0 for ph in phases}
        successors = {ph.id: [] for ph in phases}

        for ph in phases:
            for dep in ph.dependencies.all():
                pred_id = dep.predecessor_phase_id
                if pred_id in phase_ids:
                    in_deg[ph.id] += 1
                    successors[pred_id].append(ph.id)

        phase_by_id = {ph.id: ph for ph in phases}
        PR = DependencyGraphService.PRIORITY_RANK
        CR = DependencyGraphService.CONFIDENCE_RANK

        def _key(ph_id):
            ph = phase_by_id[ph_id]
            proj = proj_by_phase_id.get(ph.plan_project_team.plan_project_id)
            dates_strict = 0 if (proj and proj.dates_strict) else 1
            pri = PR.get(proj.effective_priority if proj else None, 4)
            con = CR.get(proj.effective_confidence if proj else None, 4)
            end_pos = ph.end_sprint.sprint_number if ph.end_sprint else 9999
            disp = proj.display_order if proj else 0
            return (dates_strict, pri, con, end_pos, disp, ph.sequence_order)

        heap = []
        for ph_id, deg in in_deg.items():
            if deg == 0:
                heapq.heappush(heap, (_key(ph_id), ph_id))

        result = []
        while heap:
            _, ph_id = heapq.heappop(heap)
            result.append(phase_by_id[ph_id])
            for succ_id in successors[ph_id]:
                in_deg[succ_id] -= 1
                if in_deg[succ_id] == 0:
                    heapq.heappush(heap, (_key(succ_id), succ_id))

        seen = {ph.id for ph in result}
        for ph in phases:
            if ph.id not in seen:
                result.append(ph)
        return result

    @staticmethod
    def earliest_start(phase, completed, sprint_nums):
        """Return the earliest sprint_number this phase can start after its dependencies."""
        base = phase.start_sprint.sprint_number if phase.start_sprint else (sprint_nums[0] if sprint_nums else 1)
        for dep in phase.dependencies.all():
            info = completed.get(dep.predecessor_phase_id, {})
            lag = dep.lag_sprints
            dep_type = dep.dependency_type
            if dep_type == 'FS':
                base = max(base, info.get('end', 0) + 1 + lag)
            elif dep_type == 'SS':
                base = max(base, info.get('start', 0) + lag)
        return base


class AutoAssignService:
    @staticmethod
    def select_member(team_members, sprint_nums, member_alloc):
        """Return team member with lowest total allocated days across given sprints."""
        def _load(m):
            return sum(member_alloc[m.id].get(sn, Decimal('0')) for sn in sprint_nums)
        return min(team_members, key=_load)


class AllocationSetService:

    @staticmethod
    def list_sets(version):
        from .models import ResourcePlanAllocationSet
        return list(
            ResourcePlanAllocationSet.objects.filter(version=version)
            .select_related('engine_job')
            .order_by('-created_at')
        )

    @staticmethod
    def get_set(version, set_pk):
        from .models import ResourcePlanAllocationSet
        try:
            return ResourcePlanAllocationSet.objects.select_related('version', 'engine_job').get(
                pk=set_pk, version=version
            )
        except ResourcePlanAllocationSet.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def activate(alloc_set):
        from .models import ResourcePlanAllocationSet
        version = alloc_set.version
        ResourcePlanAllocationSet.objects.filter(
            version=version, status__in=[
                ResourcePlanAllocationSet.STATUS_ACTIVE,
                ResourcePlanAllocationSet.STATUS_DRAFT,
            ]
        ).exclude(pk=alloc_set.pk).update(status=ResourcePlanAllocationSet.STATUS_SUPERSEDED)

        alloc_set.status = ResourcePlanAllocationSet.STATUS_ACTIVE
        alloc_set.activated_at = timezone.now()
        alloc_set.save(update_fields=['status', 'activated_at', 'updated_at'])
        return alloc_set

    @staticmethod
    @transaction.atomic
    def update_notes(alloc_set, notes):
        alloc_set.notes = notes or None
        alloc_set.save(update_fields=['notes', 'updated_at'])
        return alloc_set

    @staticmethod
    def get_allocations_grid(version, allocation_set_id=None, team_id=None):
        """Table 3: flat allocation rows (programme, project, team, member, phase) per sprint."""
        from apps.sprints.models import Sprint
        from .models import ResourcePlanAllocationSet, ResourcePlanAllocation

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        sprint_list = (
            list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))
            if scope else []
        )
        sprint_meta = [{'id': s.id, 'name': s.sprint_name, 'month': s.month} for s in sprint_list]

        if not allocation_set_id:
            aset = ResourcePlanAllocationSet.objects.filter(
                version=version, status=ResourcePlanAllocationSet.STATUS_ACTIVE
            ).order_by('-created_at').first()
            if not aset:
                aset = ResourcePlanAllocationSet.objects.filter(
                    version=version
                ).order_by('-created_at').first()
        else:
            try:
                aset = ResourcePlanAllocationSet.objects.get(pk=allocation_set_id, version=version)
            except ResourcePlanAllocationSet.DoesNotExist:
                return {'sprints': sprint_meta, 'rows': [], 'allocation_set_id': None}

        if not aset:
            return {'sprints': sprint_meta, 'rows': [], 'allocation_set_id': None}

        alloc_qs = (
            ResourcePlanAllocation.objects.filter(allocation_set=aset)
            .select_related(
                'programme', 'project', 'team',
                'team_member', 'team_member__employment_type',
                'placeholder_engineer', 'sprint', 'phase',
                'phase__plan_project_team__plan_project',
            )
        )
        if team_id:
            alloc_qs = alloc_qs.filter(team_id=team_id)

        sprint_index = {s.id: i for i, s in enumerate(sprint_list)}

        # Flat grouping: (prog_id, proj_id, team_id, eng_key, phase_id) → row data
        row_key_map = {}
        for alloc in alloc_qs:
            if alloc.sprint_id not in sprint_index:
                continue

            prog_name = alloc.programme.name if alloc.programme else 'Unassigned'
            proj_name = alloc.project.name if alloc.project else '—'
            team_name = alloc.team.name if alloc.team else '—'
            phase_name = alloc.phase.name if alloc.phase else '—'

            # Priority/confidence from the plan project linked via the phase
            phase_priority = None
            phase_confidence = None
            if alloc.phase and alloc.phase.plan_project_team_id:
                plan_proj = alloc.phase.plan_project_team.plan_project
                phase_priority = plan_proj.effective_priority
                phase_confidence = plan_proj.effective_confidence

            if alloc.team_member_id:
                eng_key = ('member', alloc.team_member_id)
                member_name = alloc.team_member.display_name
                member_id = alloc.team_member_id
                member_type = 'member'
                member_employment_type = (
                    alloc.team_member.employment_type.name
                    if alloc.team_member.employment_type_id else None
                )
            else:
                eng_key = ('placeholder', alloc.placeholder_engineer_id)
                member_name = alloc.placeholder_engineer.name if alloc.placeholder_engineer else 'Auto'
                member_id = alloc.placeholder_engineer_id
                member_type = 'placeholder'
                member_employment_type = None

            row_key = (alloc.programme_id, alloc.project_id, alloc.team_id, eng_key, alloc.phase_id)
            if row_key not in row_key_map:
                row_key_map[row_key] = {
                    'programme_name': prog_name,
                    'project_id': alloc.project_id,
                    'project_name': proj_name,
                    'team_id': alloc.team_id,
                    'team_name': team_name,
                    'phase_id': alloc.phase_id,
                    'member_id': member_id,
                    'member_type': member_type,
                    'member_name': member_name,
                    'member_employment_type': member_employment_type,
                    'phase_name': phase_name,
                    'phase_priority': phase_priority,
                    'phase_confidence': phase_confidence,
                    'cells': {},
                }
            sid = alloc.sprint_id
            existing = row_key_map[row_key]['cells'].get(sid)
            if existing is None:
                row_key_map[row_key]['cells'][sid] = {
                    'days': float(alloc.effective_days),
                    'allocation_id': alloc.id,
                    'is_override': alloc.override_days is not None,
                    'multi': False,
                }
            else:
                existing['days'] += float(alloc.effective_days)
                existing['allocation_id'] = None
                existing['multi'] = True

        flat_rows = []
        for (rk, row_data) in sorted(
            row_key_map.items(),
            key=lambda kv: (
                kv[1]['programme_name'], kv[1]['project_name'],
                kv[1]['team_name'], kv[1]['member_name'], kv[1]['phase_name']
            )
        ):
            cells = []
            for s in sprint_list:
                cd = row_data['cells'].get(s.id)
                if cd:
                    cells.append({
                        'sprint_id': s.id,
                        'days': round(cd['days'], 2),
                        'allocation_id': cd['allocation_id'],
                        'is_override': cd['is_override'],
                        'multi': cd['multi'],
                    })
                else:
                    cells.append({
                        'sprint_id': s.id,
                        'days': 0.0,
                        'allocation_id': None,
                        'is_override': False,
                        'multi': False,
                    })
            flat_rows.append({
                'programme_name': row_data['programme_name'],
                'project_id': row_data['project_id'],
                'project_name': row_data['project_name'],
                'team_id': row_data['team_id'],
                'team_name': row_data['team_name'],
                'phase_id': row_data.get('phase_id'),
                'member_id': row_data['member_id'],
                'member_type': row_data['member_type'],
                'member_name': row_data['member_name'],
                'member_employment_type': row_data.get('member_employment_type'),
                'phase_name': row_data['phase_name'],
                'phase_priority': row_data.get('phase_priority'),
                'phase_confidence': row_data.get('phase_confidence'),
                'cells': cells,
                'total_days': round(sum(c['days'] for c in cells), 2),
            })

        return {'sprints': sprint_meta, 'rows': flat_rows, 'allocation_set_id': aset.id}

    @staticmethod
    def get_allocated_capacity_grid(version, allocation_set_id=None, team_id=None):
        """Table 4: allocated days + capacity per engineer per sprint."""
        from apps.sprints.models import Sprint
        from .models import ResourcePlanAllocationSet, ResourcePlanAllocation, ResourcePlanMemberCapacity

        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        sprint_list = (
            list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))
            if scope else []
        )
        sprint_meta = [{'id': s.id, 'name': s.sprint_name, 'month': s.month} for s in sprint_list]

        if not allocation_set_id:
            aset = ResourcePlanAllocationSet.objects.filter(
                version=version, status=ResourcePlanAllocationSet.STATUS_ACTIVE
            ).order_by('-created_at').first()
            if not aset:
                aset = ResourcePlanAllocationSet.objects.filter(version=version).order_by('-created_at').first()
        else:
            try:
                aset = ResourcePlanAllocationSet.objects.get(pk=allocation_set_id, version=version)
            except ResourcePlanAllocationSet.DoesNotExist:
                return {'sprints': sprint_meta, 'rows': [], 'allocation_set_id': None}

        if not aset:
            return {'sprints': sprint_meta, 'rows': [], 'allocation_set_id': None}

        alloc_qs = (
            ResourcePlanAllocation.objects.filter(allocation_set=aset)
            .select_related('team_member', 'placeholder_engineer', 'team', 'sprint')
        )
        if team_id:
            alloc_qs = alloc_qs.filter(team_id=team_id)

        alloc_by_member = {}
        for alloc in alloc_qs:
            if alloc.team_member_id:
                key = ('member', alloc.team_member_id)
                label = alloc.team_member.display_name
                mid_val = alloc.team_member_id
            else:
                pe = alloc.placeholder_engineer
                slot = pe.slot_number if pe else 1
                key = ('placeholder', alloc.team_id, slot)
                label = f'Auto #{slot}' if pe else 'Auto'
                mid_val = None
            if key not in alloc_by_member:
                alloc_by_member[key] = {
                    'name': label,
                    'team_id': alloc.team_id,
                    'team_name': alloc.team.name,
                    'days': {},
                    'mid': mid_val,
                }
            sid = alloc.sprint_id
            alloc_by_member[key]['days'][sid] = alloc_by_member[key]['days'].get(sid, 0.0) + float(alloc.effective_days)

        member_ids = [k[1] for k in alloc_by_member if k[0] == 'member']
        sprint_ids = [s.id for s in sprint_list]
        cap_lookup = {}
        if member_ids:
            for rc in ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id__in=member_ids, sprint_id__in=sprint_ids
            ):
                cap_lookup[(rc.team_member_id, rc.sprint_id)] = rc

        rows = []
        for key, mdata in sorted(alloc_by_member.items(), key=lambda x: x[1]['name']):
            mtype = key[0]
            mid   = mdata['mid']
            cells = []
            for sprint in sprint_list:
                allocated = round(mdata['days'].get(sprint.id, 0.0), 2)
                rc = cap_lookup.get((mid, sprint.id)) if mtype == 'member' else None
                net = float(rc.net_capacity) if rc else None
                cells.append({
                    'sprint_id': sprint.id,
                    'allocated_days': allocated,
                    'net_capacity': net,
                    'utilization_pct': round((allocated / net * 100), 1) if net else None,
                    'is_over': (allocated > net) if net is not None else False,
                    'holiday_days': float(rc.holiday_days) if rc else None,
                    'leave_days': float(rc.leave_days) if rc else None,
                    'placeholder_days': float(rc.placeholder_days) if rc else None,
                })
            rows.append({
                'member_id': mid if mtype == 'member' else None,
                'placeholder_id': True if mtype == 'placeholder' else None,
                'member_name': mdata['name'],
                'team_id': mdata['team_id'],
                'team_name': mdata['team_name'],
                'cells': cells,
            })

        return {'sprints': sprint_meta, 'rows': rows, 'allocation_set_id': aset.id}


class CellUpdateService:
    """Validates and persists override_days for a single ResourcePlanAllocation cell."""

    @staticmethod
    @transaction.atomic
    def update_cell(version, alloc_pk, days):
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        from .models import ResourcePlanAllocation, ResourcePlanAllocationSet, ResourcePlanVersionProject

        try:
            raw = Decimal(str(days))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({"days": "Invalid value."})

        d = raw.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if d < Decimal('0') or d > Decimal('10'):
            raise ValidationError({"days": "Value must be between 0 and 10."})

        try:
            alloc = ResourcePlanAllocation.objects.select_related(
                'allocation_set__engine_job', 'project', 'sprint',
                'team_member', 'placeholder_engineer',
            ).get(pk=alloc_pk, allocation_set__version=version)
        except ResourcePlanAllocation.DoesNotExist:
            raise ValidationError({"detail": "Allocation not found."})

        if alloc.allocation_set.status == ResourcePlanAllocationSet.STATUS_ACTIVE:
            raise ValidationError({"detail": "Cannot edit cells in an ACTIVE allocation set."})

        # Task 4: validate total allocated days ≤ 10 per engineer per sprint
        if alloc.team_member_id:
            from django.db.models import Sum, Case, When, F as DbF
            others_total = (
                ResourcePlanAllocation.objects.filter(
                    allocation_set=alloc.allocation_set,
                    team_member=alloc.team_member,
                    sprint=alloc.sprint,
                ).exclude(pk=alloc.pk)
                .aggregate(total=Sum(Case(
                    When(override_days__isnull=False, then=DbF('override_days')),
                    default=DbF('engine_days'),
                )))['total'] or Decimal('0')
            )
            if others_total + d > Decimal('10'):
                raise ValidationError({"days": f"Total for this sprint would be {float(others_total + d):.2f}d — engineer cannot exceed 10d per sprint."})

        if d == alloc.engine_days:
            alloc.override_days = None
            alloc.overridden_at = None
        else:
            alloc.override_days = d
            alloc.overridden_at = timezone.now()
        alloc.save(update_fields=['override_days', 'overridden_at'])

        if alloc.override_days is not None:
            ResourcePlanVersion.objects.filter(pk=version.pk).update(has_allocation_overrides=True)

        project_total = round(sum(
            float(a.effective_days)
            for a in ResourcePlanAllocation.objects.filter(
                allocation_set=alloc.allocation_set, project=alloc.project
            )
        ), 2)

        if alloc.team_member_id:
            eng_sprint_qs = ResourcePlanAllocation.objects.filter(
                allocation_set=alloc.allocation_set,
                sprint=alloc.sprint,
                team_member_id=alloc.team_member_id,
            )
        else:
            eng_sprint_qs = ResourcePlanAllocation.objects.filter(
                allocation_set=alloc.allocation_set,
                sprint=alloc.sprint,
                placeholder_engineer_id=alloc.placeholder_engineer_id,
            )
        eng_sprint_allocated = round(sum(float(a.effective_days) for a in eng_sprint_qs), 2)

        plan_project = ResourcePlanVersionProject.objects.filter(
            version=version, project=alloc.project
        ).first()
        threshold_info = None
        if plan_project:
            threshold_info = {
                'project_id': alloc.project_id,
                'project_name': alloc.project.name,
                'is_over_threshold': plan_project.is_over_threshold,
                'is_under_threshold': plan_project.is_under_threshold,
                'threshold_pct': float(version.threshold_pct or 0),
            }

        conflict_count = 0
        if alloc.allocation_set.engine_job and alloc.allocation_set.engine_job.validation_result:
            conflict_count = alloc.allocation_set.engine_job.validation_result.get('conflict_count', 0)

        # Re-evaluate threshold breaches when effective days change
        try:
            ConflictDetectionService.refresh_threshold_for_alloc_set(alloc.allocation_set)
        except Exception:
            pass

        return {
            'allocation_id': alloc.pk,
            'sprint_id': alloc.sprint_id,
            'project_id': alloc.project_id,
            'member_id': alloc.team_member_id,
            'member_type': 'member' if alloc.team_member_id else 'placeholder',
            'effective_days': float(alloc.effective_days),
            'is_override': alloc.override_days is not None,
            'project_total': project_total,
            'engineer_sprint_allocated': eng_sprint_allocated,
            'threshold_info': threshold_info,
            'conflict_count': conflict_count,
        }


class CellCreateService:
    """Creates a new ResourcePlanAllocation row for a cell that has no engine allocation."""

    @staticmethod
    @transaction.atomic
    def create_cell(version, data):
        from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
        from .models import (
            ResourcePlanAllocation, ResourcePlanAllocationSet,
            PlanPhase, PlanAssignment, ResourcePlanPlaceholderEngineer,
        )
        from apps.sprints.models import Sprint

        try:
            raw = Decimal(str(data.get('days', 0)))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({"days": "Invalid value."})

        d = raw.quantize(Decimal('0.25'), rounding=ROUND_HALF_UP)
        if d < Decimal('0') or d > Decimal('10'):
            raise ValidationError({"days": "Value must be between 0 and 10."})

        if d == Decimal('0'):
            return {'allocation_id': None, 'effective_days': 0.0, 'is_override': False,
                    'project_total': 0.0, 'engineer_sprint_allocated': 0.0}

        aset_id = data.get('allocation_set_id')
        try:
            aset = ResourcePlanAllocationSet.objects.get(pk=aset_id, version=version)
        except ResourcePlanAllocationSet.DoesNotExist:
            raise ValidationError({"detail": "Allocation set not found."})
        if aset.status == ResourcePlanAllocationSet.STATUS_ACTIVE:
            raise ValidationError({"detail": "Cannot edit cells in an ACTIVE allocation set."})

        phase_id = data.get('phase_id')
        try:
            phase = PlanPhase.objects.select_related(
                'plan_project_team__plan_project__project__programme',
                'plan_project_team__team',
            ).get(pk=phase_id, plan_project_team__plan_project__version=version)
        except PlanPhase.DoesNotExist:
            raise ValidationError({"detail": "Phase not found."})

        plan_proj_team = phase.plan_project_team
        plan_proj = plan_proj_team.plan_project
        project = plan_proj.project
        team = plan_proj_team.team
        programme = getattr(project, 'programme', None)

        sprint_id = data.get('sprint_id')
        try:
            sprint = Sprint.objects.get(pk=sprint_id)
        except Sprint.DoesNotExist:
            raise ValidationError({"detail": "Sprint not found."})

        member_id = data.get('member_id')
        member_type = data.get('member_type', 'member')
        team_member = None
        placeholder_engineer = None

        if member_type == 'member':
            from apps.team_members.models import TeamMember
            try:
                team_member = TeamMember.objects.get(pk=member_id)
            except TeamMember.DoesNotExist:
                raise ValidationError({"detail": "Team member not found."})
        else:
            try:
                placeholder_engineer = ResourcePlanPlaceholderEngineer.objects.get(pk=member_id)
            except ResourcePlanPlaceholderEngineer.DoesNotExist:
                raise ValidationError({"detail": "Placeholder engineer not found."})

        if team_member:
            from django.db.models import Sum, Case, When, F as DbF
            existing_total = (
                ResourcePlanAllocation.objects.filter(
                    allocation_set=aset,
                    team_member=team_member,
                    sprint=sprint,
                )
                .aggregate(total=Sum(Case(
                    When(override_days__isnull=False, then=DbF('override_days')),
                    default=DbF('engine_days'),
                )))['total'] or Decimal('0')
            )
            if existing_total + d > Decimal('10'):
                raise ValidationError({"days": f"Total for this sprint would be {float(existing_total + d):.2f}d — engineer cannot exceed 10d per sprint."})

        alloc = ResourcePlanAllocation.objects.create(
            allocation_set=aset,
            programme=programme,
            project=project,
            team=team,
            team_member=team_member,
            placeholder_engineer=placeholder_engineer,
            sprint=sprint,
            phase=phase,
            assignment=None,
            assignment_type=PlanAssignment.ASSIGN_ENGINEER,
            includes_in_budget=True,
            engine_days=Decimal('0'),
            override_days=d,
            overridden_at=timezone.now(),
        )
        ResourcePlanVersion.objects.filter(pk=version.pk).update(has_allocation_overrides=True)

        project_total = round(sum(
            float(a.effective_days)
            for a in ResourcePlanAllocation.objects.filter(
                allocation_set=aset, project=project
            )
        ), 2)

        if team_member:
            eng_sprint_qs = ResourcePlanAllocation.objects.filter(
                allocation_set=aset, sprint=sprint, team_member=team_member,
            )
        else:
            eng_sprint_qs = ResourcePlanAllocation.objects.filter(
                allocation_set=aset, sprint=sprint, placeholder_engineer=placeholder_engineer,
            )
        eng_sprint_allocated = round(sum(float(a.effective_days) for a in eng_sprint_qs), 2)

        try:
            ConflictDetectionService.refresh_threshold_for_alloc_set(aset)
        except Exception:
            pass

        return {
            'allocation_id': alloc.pk,
            'sprint_id': alloc.sprint_id,
            'project_id': alloc.project_id,
            'member_id': alloc.team_member_id,
            'member_type': 'member' if team_member else 'placeholder',
            'effective_days': float(alloc.effective_days),
            'is_override': True,
            'project_total': project_total,
            'engineer_sprint_allocated': eng_sprint_allocated,
        }


class AllocationEngineService:
    """Orchestrates Steps 5-8 of the engine: dependency sort, ramp distribution, auto-assign, conflicts."""

    @staticmethod
    def run(job):
        """Create a ResourcePlanAllocationSet and populate ResourcePlanAllocation rows."""
        from .models import (
            ResourcePlanAllocationSet, ResourcePlanAllocation,
            ResourcePlanPlaceholderEngineer,
        )
        from collections import defaultdict

        version = job.version
        scope = ResourcePlanScope.objects.filter(plan_group=version.plan_group).select_related('financial_year').first()
        if not scope:
            return None, []

        from apps.sprints.models import Sprint
        sprints = list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))
        sprint_nums = [s.sprint_number for s in sprints]
        sprints_by_num = {s.sprint_number: s for s in sprints}

        # Determine the minimum sprint number based on the active sprint
        active_sprint_obj = Sprint.objects.filter(is_active=True).first()
        if active_sprint_obj and active_sprint_obj.sprint_number in sprint_nums:
            if job.include_current_sprint:
                min_sprint_num = active_sprint_obj.sprint_number
            else:
                min_sprint_num = active_sprint_obj.sprint_number + 1
        else:
            min_sprint_num = sprint_nums[0] if sprint_nums else 1

        projects = list(
            ResourcePlanVersionProject.objects.filter(version=version)
            .select_related('project__programme', 'start_sprint', 'end_sprint')
            .prefetch_related(
                'teams__team',
                'teams__phases__segments',
                'teams__phases__dependencies',
                'teams__phases__pauses',
                'teams__phases__assignments__team_member',
            )
        )

        all_phases = []
        proj_by_phase_id = {}
        team_entry_by_phase_id = {}
        phases_per_team_entry = defaultdict(list)

        for proj in projects:
            for te in proj.teams.all():
                for ph in te.phases.all():
                    all_phases.append(ph)
                    proj_by_phase_id[ph.id] = proj
                    team_entry_by_phase_id[ph.id] = te
                    phases_per_team_entry[te.id].append(ph.id)

        if not all_phases or not sprints:
            return None, []

        sorted_phases = DependencyGraphService.topological_sort(all_phases, proj_by_phase_id)

        alloc_set = ResourcePlanAllocationSet.objects.create(
            version=version,
            engine_job=job,
            status=ResourcePlanAllocationSet.STATUS_DRAFT,
        )

        member_alloc = defaultdict(lambda: defaultdict(Decimal))
        completed = {}
        to_create = []
        placeholder_slots = defaultdict(int)
        conflicts = []

        for phase in sorted_phases:
            proj = proj_by_phase_id[phase.id]
            te = team_entry_by_phase_id[phase.id]
            programme = proj.project.programme

            earliest = DependencyGraphService.earliest_start(phase, completed, sprint_nums)
            phase_start = max(earliest, min_sprint_num)
            if phase.start_sprint:
                phase_start = max(phase_start, phase.start_sprint.sprint_number)

            if phase.end_sprint:
                phase_end = phase.end_sprint.sprint_number
            elif proj.end_sprint:
                phase_end = proj.end_sprint.sprint_number
            else:
                phase_end = sprint_nums[-1] if sprint_nums else 1

            phase_start = max(phase_start, min_sprint_num)
            phase_end = min(phase_end, sprint_nums[-1] if sprint_nums else 9999)

            if phase_start > phase_end:
                completed[phase.id] = {'start': phase_start, 'end': phase_start}
                continue

            paused_nums = set()
            for pause in phase.pauses.all():
                if pause.resume_sprint:
                    paused_nums.update(range(pause.pause_from.sprint_number, pause.resume_sprint.sprint_number))
                elif pause.pause_sprint_count:
                    p_from = pause.pause_from.sprint_number
                    paused_nums.update(range(p_from, p_from + pause.pause_sprint_count))

            active_nums = [sn for sn in sprint_nums if phase_start <= sn <= phase_end and sn not in paused_nums]
            if not active_nums:
                completed[phase.id] = {'start': phase_start, 'end': phase_end}
                continue

            assignments = list(phase.assignments.all())
            if not assignments:
                from types import SimpleNamespace
                assignments = [SimpleNamespace(
                    pk=None,
                    auto_assign=True,
                    team_member_id=None,
                    team_member=None,
                    split_value=None,
                    assignment_type=PlanAssignment.ASSIGN_ENGINEER,
                    includes_in_budget=True,
                )]

            if hasattr(phase, 'days_effort') and phase.days_effort is not None:
                phase_total = Decimal(str(phase.days_effort))
            else:
                n_phases = len(phases_per_team_entry.get(te.id, [1]))
                team_days = te.allocated_days or Decimal('0')
                phase_total = team_days / max(n_phases, 1)

            segments = None
            if phase.ramp_pattern == PlanPhase.RAMP_CUSTOM:
                segments = list(phase.segments.order_by('segment_order'))

            named = [a for a in assignments if not a.auto_assign and a.team_member_id]
            auto = [a for a in assignments if a.auto_assign]
            n_total = len(assignments) or 1

            for asgn in assignments:
                if phase.split_mode == PlanPhase.SPLIT_DAYS and asgn.split_value:
                    alloc_nums = active_nums
                    sprint_days = [asgn.split_value] * len(alloc_nums)
                    effective_max = Decimal('10')
                    _do_cap = False  # user-specified days per sprint; never override
                else:
                    if phase.split_mode == PlanPhase.SPLIT_PERCENT and asgn.split_value:
                        share = Decimal(str(asgn.split_value)) / Decimal('100')
                    elif phase.split_mode == PlanPhase.SPLIT_EQUAL:
                        share = Decimal('1') / Decimal(str(n_total))
                    else:
                        share = Decimal('1') / Decimal(str(n_total))
                    phase_share = phase_total * share

                    # "Complete early": trim active_nums to fewest sprints needed.
                    # If max_days_per_sprint not set, default to 10d (full sprint) so
                    # days are concentrated rather than spread across the entire FY.
                    alloc_nums = active_nums
                    effective_max = (
                        Decimal(str(phase.max_days_per_sprint))
                        if phase.max_days_per_sprint
                        else Decimal('10')
                    )
                    if phase_share > Decimal('0') and effective_max > 0:
                        needed = max(1, int(_ceil(float(phase_share) / float(effective_max))))
                        alloc_nums = active_nums[:needed]

                    sprint_days = RampDistributionService.distribute(
                        phase_share, len(alloc_nums), phase.ramp_pattern, segments, effective_max
                    )
                    _do_cap = True

                # Sprints in the active range that won't receive allocated days —
                # create 0-day records so the grid can show them as editable.
                _alloc_set = set(alloc_nums)
                zero_nums = [sn for sn in active_nums if sn not in _alloc_set]

                if asgn.auto_assign:
                    from apps.team_members.models import TeamMember
                    team_members = list(TeamMember.objects.filter(team=te.team, is_active=True))
                    _asgn_fk = asgn if asgn.pk else None
                    if team_members:
                        member = AutoAssignService.select_member(team_members, alloc_nums, member_alloc)
                        if _do_cap:
                            sprint_days = [
                                max(Decimal('0'), min(d, effective_max - member_alloc[member.id][sn]))
                                for sn, d in zip(alloc_nums, sprint_days)
                            ]
                        for sn, d in zip(alloc_nums, sprint_days):
                            member_alloc[member.id][sn] += d
                            to_create.append(ResourcePlanAllocation(
                                allocation_set=alloc_set, programme=programme,
                                project=proj.project, team=te.team, team_member=member,
                                sprint=sprints_by_num[sn], phase=phase, assignment=_asgn_fk,
                                assignment_type=asgn.assignment_type,
                                includes_in_budget=asgn.includes_in_budget, engine_days=d,
                            ))
                        for sn in zero_nums:
                            to_create.append(ResourcePlanAllocation(
                                allocation_set=alloc_set, programme=programme,
                                project=proj.project, team=te.team, team_member=member,
                                sprint=sprints_by_num[sn], phase=phase, assignment=_asgn_fk,
                                assignment_type=asgn.assignment_type,
                                includes_in_budget=asgn.includes_in_budget, engine_days=Decimal('0'),
                            ))
                    else:
                        key = (version.id, te.team_id, phase.id)
                        placeholder_slots[key] += 1
                        pe, _ = ResourcePlanPlaceholderEngineer.objects.get_or_create(
                            version=version, team=te.team, phase=phase,
                            slot_number=placeholder_slots[key],
                            defaults={
                                'name': f'Auto #{placeholder_slots[key]}',
                                'assignment_type': asgn.assignment_type,
                            },
                        )
                        for sn, d in zip(alloc_nums, sprint_days):
                            to_create.append(ResourcePlanAllocation(
                                allocation_set=alloc_set, programme=programme,
                                project=proj.project, team=te.team, placeholder_engineer=pe,
                                sprint=sprints_by_num[sn], phase=phase, assignment=_asgn_fk,
                                assignment_type=asgn.assignment_type,
                                includes_in_budget=asgn.includes_in_budget, engine_days=d,
                            ))
                        for sn in zero_nums:
                            to_create.append(ResourcePlanAllocation(
                                allocation_set=alloc_set, programme=programme,
                                project=proj.project, team=te.team, placeholder_engineer=pe,
                                sprint=sprints_by_num[sn], phase=phase, assignment=_asgn_fk,
                                assignment_type=asgn.assignment_type,
                                includes_in_budget=asgn.includes_in_budget, engine_days=Decimal('0'),
                            ))
                else:
                    member = asgn.team_member
                    if _do_cap:
                        sprint_days = [
                            max(Decimal('0'), min(d, effective_max - member_alloc[member.id][sn]))
                            for sn, d in zip(alloc_nums, sprint_days)
                        ]
                    for sn, d in zip(alloc_nums, sprint_days):
                        member_alloc[member.id][sn] += d
                        to_create.append(ResourcePlanAllocation(
                            allocation_set=alloc_set, programme=programme,
                            project=proj.project, team=te.team, team_member=member,
                            sprint=sprints_by_num[sn], phase=phase, assignment=asgn,
                            assignment_type=asgn.assignment_type,
                            includes_in_budget=asgn.includes_in_budget, engine_days=d,
                        ))
                    for sn in zero_nums:
                        to_create.append(ResourcePlanAllocation(
                            allocation_set=alloc_set, programme=programme,
                            project=proj.project, team=te.team, team_member=member,
                            sprint=sprints_by_num[sn], phase=phase, assignment=asgn,
                            assignment_type=asgn.assignment_type,
                            includes_in_budget=asgn.includes_in_budget, engine_days=Decimal('0'),
                        ))

            completed[phase.id] = {'start': phase_start, 'end': phase_end}

        ResourcePlanAllocation.objects.bulk_create(to_create, batch_size=500)

        conflicts = AllocationEngineService._detect_conflicts(version, alloc_set, member_alloc, sprints)
        return alloc_set, conflicts

    @staticmethod
    def _detect_conflicts(version, alloc_set, member_alloc, sprints):
        from .models import ResourcePlanMemberCapacity
        conflicts = []
        sprint_by_num = {s.sprint_number: s for s in sprints}
        member_ids = list(member_alloc.keys())
        if not member_ids:
            return conflicts

        cap_lookup = {
            (rc.team_member_id, rc.sprint_id): rc.net_capacity
            for rc in ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id__in=member_ids
            )
        }

        for member_id, sprint_data in member_alloc.items():
            for sprint_num, days in sprint_data.items():
                sprint = sprint_by_num.get(sprint_num)
                if not sprint:
                    continue
                net = cap_lookup.get((member_id, sprint.id))
                if net is not None and days > net:
                    conflicts.append({
                        'severity': 'ERROR',
                        'entity': 'member',
                        'member_id': member_id,
                        'sprint_id': sprint.id,
                        'sprint_name': sprint.sprint_name,
                        'allocated_days': float(days),
                        'net_capacity': float(net),
                        'message': f'Over-capacity: {float(days):.1f}d allocated vs {float(net):.1f}d available.',
                    })
        return conflicts


class ConflictDetectionService:
    """Detects all conflict types during engine run and persists Conflict records."""

    @staticmethod
    @transaction.atomic
    def detect_and_persist(version, alloc_set, job):
        from .models import (
            Conflict, ResourcePlanMemberCapacity, ResourcePlanVersionProject,
            ResourcePlanAllocation, ResourcePlanScope,
            ResourcePlanPlaceholderEngineer, ManpowerRequest,
        )
        from collections import defaultdict
        from django.db.models import Sum
        from apps.sprints.models import Sprint

        Conflict.objects.filter(allocation_set=alloc_set).delete()

        conflicts_to_create = []

        # Build member_alloc from existing ResourcePlanAllocation records
        member_alloc = defaultdict(lambda: defaultdict(Decimal))
        alloc_qs_members = ResourcePlanAllocation.objects.filter(
            allocation_set=alloc_set
        ).select_related('sprint', 'team_member')
        for alloc in alloc_qs_members:
            if alloc.team_member_id:
                member_alloc[alloc.team_member_id][alloc.sprint.sprint_number] += alloc.engine_days

        # Get sprints from scope
        scope = ResourcePlanScope.objects.filter(
            plan_group=version.plan_group
        ).select_related('financial_year').first()
        sprints = list(
            Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number')
        ) if scope else []

        sprint_by_num = {s.sprint_number: s for s in sprints}
        sprint_by_id  = {s.id: s for s in sprints}

        # ── 1. CAPACITY_EXCEEDED ──────────────────────────────────────────────
        member_ids = list(member_alloc.keys())
        sprint_ids = [s.id for s in sprints]
        cap_lookup = {}
        if member_ids:
            for rc in ResourcePlanMemberCapacity.objects.filter(
                version=version, team_member_id__in=member_ids, sprint_id__in=sprint_ids
            ):
                cap_lookup[(rc.team_member_id, rc.sprint_id)] = rc

        for member_id, sprint_data in member_alloc.items():
            for sprint_num, days in sprint_data.items():
                sprint = sprint_by_num.get(sprint_num)
                if not sprint:
                    continue
                rc = cap_lookup.get((member_id, sprint.id))
                if rc is not None and days > rc.net_capacity:
                    over_by = float(days - rc.net_capacity)
                    conflicts_to_create.append(Conflict(
                        allocation_set=alloc_set,
                        engine_job=job,
                        conflict_type=Conflict.CAPACITY_EXCEEDED,
                        severity=Conflict.SEVERITY_ERROR,
                        affected_team_member_id=member_id,
                        affected_sprint=sprint,
                        description=(
                            f'Over-capacity in {sprint.sprint_name}: '
                            f'{float(days):.2f}d allocated vs {float(rc.net_capacity):.2f}d available.'
                        ),
                        engine_data={
                            'over_by': round(over_by, 2),
                            'allocated_days': round(float(days), 2),
                            'net_capacity': round(float(rc.net_capacity), 2),
                            'sprint_name': sprint.sprint_name,
                        },
                    ))

        # ── 2. THRESHOLD_BREACH (over & under) ────────────────────────────────
        from django.db.models import Q, Case, When, F
        alloc_project_qs = (
            ResourcePlanAllocation.objects.filter(allocation_set=alloc_set)
            .values('project_id')
            .annotate(total=Sum(
                Case(When(override_days__isnull=False, then=F('override_days')), default=F('engine_days'))
            ))
        )
        project_totals = {row['project_id']: Decimal(str(row['total'] or 0)) for row in alloc_project_qs}

        for vp in ResourcePlanVersionProject.objects.filter(version=version).select_related('project').prefetch_related('teams'):
            # Use sum of configured team allocated_days as the reference (not basis/days_required)
            # This avoids false-positive breaches when some teams lack phases
            team_days_total = sum(te.allocated_days or Decimal('0') for te in vp.teams.all())
            if not team_days_total:
                if not vp.days_required:
                    continue
                team_days_total = Decimal(str(vp.days_required))
            req = team_days_total
            threshold = Decimal(str(version.threshold_pct or 10))
            total = project_totals.get(vp.project_id, Decimal('0'))
            pct_diff = ((total - req) / req * 100) if req else Decimal('0')

            if abs(pct_diff) > threshold:
                direction = 'over' if pct_diff > 0 else 'under'
                conflicts_to_create.append(Conflict(
                    allocation_set=alloc_set,
                    engine_job=job,
                    conflict_type=Conflict.THRESHOLD_BREACH,
                    severity=Conflict.SEVERITY_WARNING,
                    affected_project=vp.project,
                    description=(
                        f'{vp.project.name}: {float(total):.1f}d allocated is '
                        f'{abs(float(pct_diff)):.1f}% {direction} the required {float(req):.1f}d '
                        f'(threshold {float(threshold):.0f}%).'
                    ),
                    engine_data={
                        'allocated': float(total),
                        'required': float(req),
                        'pct_diff': round(float(pct_diff), 1),
                        'direction': direction,
                        'threshold_pct': float(threshold),
                    },
                ))

        # ── 3. TIMELINE_BREACH: phases that produced no allocation rows ───────────
        # Engine now defaults no-assignment phases to auto-assign ENGINEER, so any
        # phase with zero rows was skipped entirely (expired sprint window, all
        # sprints paused, or phase_start > phase_end after clamping to active sprint).
        phase_ids_with_rows = set(
            ResourcePlanAllocation.objects.filter(
                allocation_set=alloc_set,
            ).values_list('phase_id', flat=True).distinct()
        )
        for _vp in (
            ResourcePlanVersionProject.objects.filter(version=version)
            .select_related('project')
            .prefetch_related('teams__phases', 'teams__team')
        ):
            for _te in _vp.teams.all():
                for _ph in _te.phases.all():
                    if _ph.id not in phase_ids_with_rows:
                        conflicts_to_create.append(Conflict(
                            allocation_set=alloc_set,
                            engine_job=job,
                            conflict_type=Conflict.TIMELINE_BREACH,
                            severity=Conflict.SEVERITY_ERROR,
                            affected_project=_vp.project,
                            affected_phase=_ph,
                            affected_team=_te.team,
                            description=(
                                f'{_vp.project.name} · {_ph.name} ({_te.team.name}): '
                                f'assignments are configured but no allocations were '
                                f'created — the phase or project end sprint is likely '
                                f'before the current active sprint.'
                            ),
                            engine_data={},
                        ))

        Conflict.objects.bulk_create(conflicts_to_create)

        # ── 4. UNRESOLVABLE_GAP: auto-placeholder engineers ──────────────────────
        # For each engine-created placeholder (no real members available), auto-create
        # an UNRESOLVABLE_GAP conflict and a ManpowerRequest so the Conflicts page
        # shows Hire/Dismiss actions for them.
        from django.db.models import Sum as _Sum, Count as _Count
        ph_alloc_data = list(
            ResourcePlanAllocation.objects.filter(
                allocation_set=alloc_set,
                placeholder_engineer__isnull=False,
            )
            .values('placeholder_engineer_id')
            .annotate(
                total_days=_Sum('engine_days'),
                sprint_count=_Count('sprint_id', distinct=True),
            )
        )
        if ph_alloc_data:
            pe_ids = [r['placeholder_engineer_id'] for r in ph_alloc_data]
            ph_map = {
                pe.id: pe
                for pe in ResourcePlanPlaceholderEngineer.objects.filter(
                    id__in=pe_ids
                ).select_related('team', 'phase')
            }
            first_sprint_map = {}
            for _a in (
                ResourcePlanAllocation.objects.filter(
                    allocation_set=alloc_set,
                    placeholder_engineer_id__in=pe_ids,
                    engine_days__gt=0,
                )
                .select_related('sprint')
                .order_by('placeholder_engineer_id', 'sprint__sprint_number')
            ):
                if _a.placeholder_engineer_id not in first_sprint_map:
                    first_sprint_map[_a.placeholder_engineer_id] = _a.sprint

            # Group entries by (team_id, slot_number) to create one ManpowerRequest per slot
            from collections import defaultdict
            slot_groups = defaultdict(list)
            for row in ph_alloc_data:
                pe_id = row['placeholder_engineer_id']
                pe = ph_map.get(pe_id)
                if not pe:
                    continue
                slot_key = (pe.team_id, pe.slot_number)
                slot_groups[slot_key].append((row, pe))

            for slot_key, entries in slot_groups.items():
                # Sort entries by first_sprint.sprint_number ascending
                def _entry_sort_key(item):
                    _, _pe = item
                    fs = first_sprint_map.get(_pe.id)
                    return fs.sprint_number if fs else 999999
                entries_sorted = sorted(entries, key=_entry_sort_key)

                # Accumulate totals across all phases for this slot
                total_days_sum = Decimal('0')
                sprint_count_sum = 0
                earliest_conflict = None

                for row, pe in entries_sorted:
                    total_days = Decimal(str(row['total_days'] or 0))
                    sprint_count = row['sprint_count'] or 1
                    first_sprint = first_sprint_map.get(pe.id)
                    phase_name = pe.phase.name if pe.phase else 'phase'
                    conflict = Conflict.objects.create(
                        allocation_set=alloc_set,
                        engine_job=job,
                        conflict_type=Conflict.UNRESOLVABLE_GAP,
                        severity=Conflict.SEVERITY_ERROR,
                        affected_team=pe.team,
                        affected_phase=pe.phase,
                        affected_sprint=first_sprint,
                        description=(
                            f'{pe.team.name}: no available engineer for "{phase_name}" — '
                            f'{pe.name} auto-assigned ({float(total_days):.1f}d over '
                            f'{sprint_count} sprint{"s" if sprint_count != 1 else ""}). '
                            f'Hire from {first_sprint.sprint_name if first_sprint else "the required sprint"}.'
                        ),
                        engine_data={
                            'placeholder_name': pe.name,
                            'days_needed': float(total_days),
                            'sprints_needed': sprint_count,
                            'engine_suggested_sprint_id': first_sprint.id if first_sprint else None,
                            'engine_suggested_sprint_name': first_sprint.sprint_name if first_sprint else None,
                        },
                    )
                    total_days_sum += total_days
                    sprint_count_sum += sprint_count
                    if earliest_conflict is None:
                        earliest_conflict = conflict

                # Create ONE ManpowerRequest per slot, linked to earliest-sprint conflict
                if earliest_conflict is not None:
                    ManpowerRequest.objects.create(
                        allocation_set=alloc_set,
                        conflict=earliest_conflict,
                        team=earliest_conflict.affected_team,
                        phase=None,
                        sprints_needed=sprint_count_sum,
                        days_needed=total_days_sum,
                    )

        return list(Conflict.objects.filter(allocation_set=alloc_set))

    @staticmethod
    @transaction.atomic
    def refresh_threshold_for_alloc_set(alloc_set):
        """Re-run only THRESHOLD_BREACH detection for an allocation set after manual overrides."""
        from .models import (
            Conflict, ResourcePlanAllocation, ResourcePlanVersionProject, ResourcePlanAllocationSet,
        )
        from django.db.models import Sum, Case, When, F, Q

        Conflict.objects.filter(
            allocation_set=alloc_set,
            conflict_type=Conflict.THRESHOLD_BREACH,
            status=Conflict.STATUS_OPEN,
        ).delete()

        version = alloc_set.version
        alloc_project_qs = (
            ResourcePlanAllocation.objects.filter(allocation_set=alloc_set)
            .values('project_id')
            .annotate(total=Sum(
                Case(When(override_days__isnull=False, then=F('override_days')), default=F('engine_days'))
            ))
        )
        project_totals = {row['project_id']: Decimal(str(row['total'] or 0)) for row in alloc_project_qs}

        threshold = Decimal(str(version.threshold_pct or 10))
        to_create = []
        for vp in ResourcePlanVersionProject.objects.filter(version=version).select_related('project').prefetch_related('teams'):
            team_days_total = sum(te.allocated_days or Decimal('0') for te in vp.teams.all())
            if not team_days_total:
                if not vp.days_required:
                    continue
                team_days_total = Decimal(str(vp.days_required))
            req = team_days_total
            total = project_totals.get(vp.project_id, Decimal('0'))
            pct_diff = ((total - req) / req * 100) if req else Decimal('0')
            if abs(pct_diff) > threshold:
                direction = 'over' if pct_diff > 0 else 'under'
                to_create.append(Conflict(
                    allocation_set=alloc_set,
                    engine_job=alloc_set.engine_job,
                    conflict_type=Conflict.THRESHOLD_BREACH,
                    severity=Conflict.SEVERITY_WARNING,
                    affected_project=vp.project,
                    description=(
                        f'{vp.project.name}: {float(total):.1f}d allocated is '
                        f'{abs(float(pct_diff)):.1f}% {direction} the required {float(req):.1f}d '
                        f'(threshold {float(threshold):.0f}%).'
                    ),
                    engine_data={
                        'allocated': float(total),
                        'required': float(req),
                        'pct_diff': round(float(pct_diff), 1),
                        'direction': direction,
                        'threshold_pct': float(threshold),
                    },
                ))
        if to_create:
            Conflict.objects.bulk_create(to_create)


class ConflictResolutionService:
    """Routes conflict resolution by resolution_type and marks conflicts resolved."""

    ALLOWED_RESOLUTIONS = {
        'CAPACITY_EXCEEDED':   ['DEPRIORITISED', 'ENGINEER_SWAPPED', 'TEAM_CHANGED', 'MANPOWER_RAISED', 'REBALANCED', 'DISMISSED'],
        'THRESHOLD_BREACH':    ['REBALANCED', 'DEPRIORITISED', 'DISMISSED'],
        'UNRESOLVABLE_GAP':    ['MANPOWER_RAISED', 'REBALANCED', 'DISMISSED'],
        'COMPETING_PRIORITY':  ['DEPRIORITISED', 'REBALANCED', 'DISMISSED'],
        'TIMELINE_BREACH':     ['TIMELINE_SHIFTED', 'MANPOWER_RAISED', 'DISMISSED'],
        'BUDGET_EXCEEDED':     ['DEPRIORITISED', 'REBALANCED', 'DISMISSED'],
        'DEPENDENCY_VIOLATED': ['TIMELINE_SHIFTED', 'DISMISSED'],
    }

    @staticmethod
    @transaction.atomic
    def resolve(conflict, resolution_type, notes=None, extra_data=None):
        from .models import Conflict
        extra_data = extra_data or {}

        allowed = ConflictResolutionService.ALLOWED_RESOLUTIONS.get(conflict.conflict_type, ['DISMISSED'])
        if resolution_type not in allowed:
            raise ValidationError({'resolution_type': f'Resolution type {resolution_type!r} not allowed for {conflict.conflict_type}.'})

        conflict.resolution_type = resolution_type
        conflict.resolution_notes = notes or ''
        conflict.status = Conflict.STATUS_DISMISSED if resolution_type == Conflict.RES_DISMISSED else Conflict.STATUS_RESOLVED
        conflict.resolved_at = timezone.now()
        conflict.save(update_fields=['resolution_type', 'resolution_notes', 'status', 'resolved_at'])

        if resolution_type == Conflict.RES_MANPOWER_RAISED:
            from .models import ManpowerRequest as _MR
            if not _MR.objects.filter(conflict=conflict).exists():
                ManpowerRequestService.create_from_conflict(conflict, extra_data)

        return conflict


class ManpowerRequestService:
    """Manages manpower requests arising from UNRESOLVABLE_GAP or MANPOWER_RAISED resolution."""

    @staticmethod
    @transaction.atomic
    def create_from_conflict(conflict, extra_data=None):
        from .models import ManpowerRequest
        extra_data = extra_data or {}

        team_id  = extra_data.get('team_id') or (conflict.affected_team_id)
        phase_id = extra_data.get('phase_id') or (conflict.affected_phase_id)
        ed = conflict.engine_data or {}

        return ManpowerRequest.objects.create(
            allocation_set=conflict.allocation_set,
            conflict=conflict,
            team_id=team_id,
            phase_id=phase_id,
            sprints_needed=extra_data.get('sprints_needed') or ed.get('sprints_needed', 1),
            days_needed=extra_data.get('days_needed') or ed.get('days_needed') or ed.get('over_by', 0),
            status=ManpowerRequest.STATUS_OPEN,
        )

    @staticmethod
    @transaction.atomic
    def hire(manpower_request, onboard_sprint_id=None, notes=None):
        """Create a PlaceholderEngineer from this manpower request."""
        from .models import ManpowerRequest, PlaceholderEngineer
        if not manpower_request.team_id:
            raise ValidationError({'detail': 'Team is required for hiring.'})

        version = manpower_request.allocation_set.version
        ph = PlaceholderEngineerService.create_from_manpower_request(
            manpower_request, onboard_sprint_id=onboard_sprint_id
        )

        manpower_request.status = ManpowerRequest.STATUS_HIRING
        manpower_request.resolution_notes = notes or ''
        manpower_request.resolved_at = timezone.now()
        manpower_request.save(update_fields=['status', 'resolution_notes', 'resolved_at'])
        return ph

    @staticmethod
    @transaction.atomic
    def rebalance(manpower_request, notes=None):
        from .models import ManpowerRequest
        manpower_request.status = ManpowerRequest.STATUS_REBALANCED
        manpower_request.resolution_notes = notes or ''
        manpower_request.resolved_at = timezone.now()
        manpower_request.save(update_fields=['status', 'resolution_notes', 'resolved_at'])
        return manpower_request

    @staticmethod
    @transaction.atomic
    def dismiss(manpower_request, notes=None):
        from .models import ManpowerRequest
        manpower_request.status = ManpowerRequest.STATUS_DISMISSED
        manpower_request.resolution_notes = notes or ''
        manpower_request.resolved_at = timezone.now()
        manpower_request.save(update_fields=['status', 'resolution_notes', 'resolved_at'])
        return manpower_request


class ConflictService:
    """List/detail CRUD helpers for Conflict and ManpowerRequest."""

    @staticmethod
    def list_conflicts(version, allocation_set_id=None, severity=None, status=None, conflict_type=None):
        from .models import Conflict, ResourcePlanAllocationSet
        if allocation_set_id:
            qs = Conflict.objects.filter(allocation_set_id=allocation_set_id, allocation_set__version=version)
        else:
            latest = ResourcePlanAllocationSet.objects.filter(version=version).order_by('-created_at').first()
            qs = Conflict.objects.filter(allocation_set=latest) if latest else Conflict.objects.none()
        if severity:
            qs = qs.filter(severity=severity)
        if status:
            qs = qs.filter(status=status)
        if conflict_type:
            qs = qs.filter(conflict_type=conflict_type)
        return qs.select_related(
            'allocation_set', 'engine_job', 'affected_project',
            'affected_phase', 'affected_team_member', 'affected_sprint', 'affected_team',
        ).order_by('status', 'severity', 'conflict_type', '-created_at')

    @staticmethod
    def get_conflict(version, conflict_id):
        from .models import Conflict
        try:
            return Conflict.objects.select_related(
                'allocation_set', 'engine_job', 'affected_project',
                'affected_phase', 'affected_team_member', 'affected_sprint', 'affected_team',
            ).get(pk=conflict_id, allocation_set__version=version)
        except Conflict.DoesNotExist:
            return None

    @staticmethod
    def get_summary(version, allocation_set_id=None):
        from .models import Conflict, ResourcePlanAllocationSet
        from django.db.models import Q, Count
        if allocation_set_id:
            qs = Conflict.objects.filter(allocation_set_id=allocation_set_id, allocation_set__version=version)
        else:
            # Use latest alloc set
            latest = ResourcePlanAllocationSet.objects.filter(version=version).order_by('-created_at').first()
            qs = Conflict.objects.filter(allocation_set=latest) if latest else Conflict.objects.none()

        totals = qs.aggregate(
            total=Count('id'),
            errors=Count('id', filter=Q(severity='ERROR')),
            warnings=Count('id', filter=Q(severity='WARNING')),
            infos=Count('id', filter=Q(severity='INFO')),
            open=Count('id', filter=Q(status='OPEN')),
            resolved=Count('id', filter=Q(status='RESOLVED')),
            dismissed=Count('id', filter=Q(status='DISMISSED')),
            open_errors=Count('id', filter=Q(severity='ERROR', status='OPEN')),
        )
        return {
            'total': totals['total'],
            'errors': totals['errors'],
            'warnings': totals['warnings'],
            'infos': totals['infos'],
            'open': totals['open'],
            'resolved': totals['resolved'],
            'dismissed': totals['dismissed'],
            'open_errors': totals['open_errors'],
            'has_blocking_errors': totals['open_errors'] > 0,
        }

    @staticmethod
    def list_manpower_requests(version, allocation_set_id=None, status=None):
        from .models import ManpowerRequest, ResourcePlanAllocationSet
        if allocation_set_id:
            qs = ManpowerRequest.objects.filter(allocation_set_id=allocation_set_id, allocation_set__version=version)
        else:
            latest = ResourcePlanAllocationSet.objects.filter(version=version).order_by('-created_at').first()
            qs = ManpowerRequest.objects.filter(allocation_set=latest) if latest else ManpowerRequest.objects.none()
        if status:
            qs = qs.filter(status=status)
        return qs.select_related('allocation_set', 'conflict', 'team', 'phase')

    @staticmethod
    def get_manpower_request(version, request_id):
        from .models import ManpowerRequest
        try:
            return ManpowerRequest.objects.select_related(
                'allocation_set', 'conflict', 'team', 'phase'
            ).get(pk=request_id, allocation_set__version=version)
        except ManpowerRequest.DoesNotExist:
            return None


class PlaceholderEngineerService:
    """Manages user-initiated hire placeholders (Phase 10)."""

    @staticmethod
    @transaction.atomic
    def create_from_manpower_request(manpower_request, onboard_sprint_id=None):
        from .models import PlaceholderEngineer, ResourcePlanScope
        from apps.sprints.models import Sprint

        version = manpower_request.allocation_set.version

        # Auto-assign sequence number: MAX within plan + 1
        from django.db.models import Max
        max_seq = PlaceholderEngineer.objects.filter(version=version).aggregate(m=Max('sequence_number'))['m'] or 0
        seq = max_seq + 1
        display_name = f'ENGINEER {seq}'

        # Determine engine-suggested sprint (first sprint after manpower request created_at)
        scope = ResourcePlanScope.objects.filter(plan_group=version.plan_group).select_related('financial_year').first()
        suggested_sprint = None
        if scope:
            suggested_sprint = Sprint.objects.filter(
                financial_year=scope.financial_year,
                start_date__gte=manpower_request.created_at.date() if hasattr(manpower_request.created_at, 'date') else None,
            ).order_by('sprint_number').first()

        onboard_sprint = None
        if onboard_sprint_id:
            try:
                onboard_sprint = Sprint.objects.get(pk=onboard_sprint_id)
            except Sprint.DoesNotExist:
                pass
        if not onboard_sprint:
            onboard_sprint = suggested_sprint

        ph = PlaceholderEngineer.objects.create(
            version=version,
            sequence_number=seq,
            display_name=display_name,
            team_id=manpower_request.team_id,
            manpower_request=manpower_request,
            onboard_sprint=onboard_sprint,
            engine_suggested_sprint=suggested_sprint,
        )

        if onboard_sprint and scope:
            PlaceholderEngineerAbsenceService.generate_absences(ph, scope)

        return ph

    @staticmethod
    @transaction.atomic
    def update_onboard_sprint(ph, onboard_sprint_id):
        from .models import PlaceholderEngineerAbsence, ResourcePlanScope
        from apps.sprints.models import Sprint

        try:
            new_sprint = Sprint.objects.get(pk=onboard_sprint_id)
        except Sprint.DoesNotExist:
            raise ValidationError({'onboard_sprint': 'Sprint not found.'})

        ph.onboard_sprint = new_sprint
        ph.save(update_fields=['onboard_sprint'])

        # Delete and regenerate absences
        ph.absences.all().delete()
        scope = ResourcePlanScope.objects.filter(plan_group=ph.version.plan_group).select_related('financial_year').first()
        if scope:
            PlaceholderEngineerAbsenceService.generate_absences(ph, scope)
        return ph

    @staticmethod
    @transaction.atomic
    def replace_with_hire(ph, team_member_id):
        from .models import PlaceholderEngineer, ResourcePlanAllocation
        from apps.team_members.models import TeamMember

        if ph.replaced_by_id:
            raise ValidationError({'detail': 'Placeholder already replaced.'})

        try:
            member = TeamMember.objects.get(pk=team_member_id)
        except TeamMember.DoesNotExist:
            raise ValidationError({'team_member': 'Team member not found.'})

        # Find allocation rows for the phase linked to the manpower request
        phase = ph.manpower_request.phase if ph.manpower_request_id else None
        if phase:
            ResourcePlanAllocation.objects.filter(
                allocation_set__version=ph.version,
                phase=phase,
                placeholder_engineer__isnull=False,
            ).update(team_member=member, placeholder_engineer=None)

        ph.replaced_by = member
        ph.replaced_at = timezone.now()
        ph.save(update_fields=['replaced_by', 'replaced_at'])
        return ph

    @staticmethod
    def get_placeholder_capacity(version, team_id=None):
        """Return capacity rows for PlaceholderEngineers in a version (for grid integration)."""
        from .models import PlaceholderEngineer, PlaceholderEngineerAbsence, ResourcePlanScope
        from apps.sprints.models import Sprint

        scope = ResourcePlanScope.objects.filter(plan_group=version.plan_group).select_related('financial_year').first()
        if not scope:
            return []

        sprint_list = list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))

        qs = PlaceholderEngineer.objects.filter(version=version, replaced_by__isnull=True)
        if team_id:
            qs = qs.filter(team_id=team_id)

        rows = []
        for ph in qs.select_related('team', 'onboard_sprint'):
            absence_map = {
                a.sprint_id: a.effective_days
                for a in ph.absences.all()
            }
            onboard_num = ph.onboard_sprint.sprint_number if ph.onboard_sprint else None
            cap_per_sprint = ph.capacity_days_per_sprint or Decimal('10')

            cells = []
            for sprint in sprint_list:
                if onboard_num and sprint.sprint_number >= onboard_num:
                    abs_days = absence_map.get(sprint.id, Decimal('0'))
                    net = max(Decimal('0'), cap_per_sprint - abs_days)
                    cells.append({
                        'sprint_id': sprint.id,
                        'working_days': str(cap_per_sprint),
                        'holiday_days': str(abs_days),
                        'leave_days': '0',
                        'placeholder_days': '0',
                        'net_capacity': str(net),
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
            rows.append({
                'hire_placeholder_id': ph.id,
                'member_name': ph.display_name,
                'team_id': ph.team_id,
                'team_name': ph.team.name,
                'cells': cells,
            })
        return rows

    @staticmethod
    def get_placeholder_absences(version, team_id=None):
        """Return absence rows for PlaceholderEngineers in a version (for grid integration)."""
        from .models import PlaceholderEngineer, ResourcePlanScope
        from apps.sprints.models import Sprint

        scope = ResourcePlanScope.objects.filter(plan_group=version.plan_group).select_related('financial_year').first()
        if not scope:
            return []
        sprint_list = list(Sprint.objects.filter(financial_year=scope.financial_year).order_by('sprint_number'))

        qs = PlaceholderEngineer.objects.filter(version=version, replaced_by__isnull=True)
        if team_id:
            qs = qs.filter(team_id=team_id)

        rows = []
        for ph in qs.select_related('team', 'onboard_sprint'):
            absence_map = {a.sprint_id: a for a in ph.absences.all()}
            onboard_num = ph.onboard_sprint.sprint_number if ph.onboard_sprint else None
            cells = []
            for sprint in sprint_list:
                if onboard_num and sprint.sprint_number >= onboard_num:
                    ab = absence_map.get(sprint.id)
                    hol = ab.effective_days if ab else Decimal('0')
                    cells.append({
                        'sprint_id': sprint.id,
                        'holiday_days': str(hol),
                        'leave_days': '0',
                        'placeholder_days': '0',
                        'total_absence': str(hol),
                    })
                else:
                    cells.append({
                        'sprint_id': sprint.id,
                        'holiday_days': None,
                        'leave_days': None,
                        'placeholder_days': '0',
                        'total_absence': None,
                    })
            rows.append({
                'hire_placeholder_id': ph.id,
                'member_name': ph.display_name,
                'team_id': ph.team_id,
                'team_name': ph.team.name,
                'cells': cells,
            })
        return rows


class PlaceholderEngineerAbsenceService:

    @staticmethod
    def generate_absences(ph, scope):
        from .models import PlaceholderEngineerAbsence
        from apps.sprints.models import Sprint
        from apps.configurations.models import Configuration

        try:
            cfg = Configuration.objects.get(code='DEFAULT_HOLIDAYS_PER_SPRINT')
            default_days = Decimal(str(cfg.value))
        except Exception:
            default_days = Decimal('0')

        if not ph.onboard_sprint:
            return

        sprints = Sprint.objects.filter(
            financial_year=scope.financial_year,
            sprint_number__gte=ph.onboard_sprint.sprint_number,
        ).order_by('sprint_number')

        to_create = []
        for sprint in sprints:
            to_create.append(PlaceholderEngineerAbsence(
                placeholder_engineer=ph,
                sprint=sprint,
                days=default_days,
                is_engine_generated=True,
            ))
        PlaceholderEngineerAbsence.objects.bulk_create(to_create, ignore_conflicts=True)

    @staticmethod
    @transaction.atomic
    def override_absence(absence, override_days, notes=None):
        from decimal import Decimal, InvalidOperation
        try:
            d = Decimal(str(override_days))
        except (InvalidOperation, TypeError):
            raise ValidationError({'override_days': 'Invalid value.'})
        if d == absence.days:
            absence.override_days = None
            absence.override_notes = None
        else:
            absence.override_days = d
            absence.override_notes = notes or ''
        absence.save(update_fields=['override_days', 'override_notes'])
        return absence
