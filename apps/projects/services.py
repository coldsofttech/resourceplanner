from decimal import Decimal, InvalidOperation
import logging
import re

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import F, Q, Prefetch, Value, CharField
from django.db.models.functions import Concat

from .utils import get_tshirt_size, get_tshirt_size_definitions
from apps.tags.services import TagService

from .engines import ProjectLabelEngineService
from .models import (
    Project,
    ProjectAttachment,
    ProjectBudget,
    ProjectBudgetHistory,
    ProjectCode,
    ProjectCollaborator,
    ProjectComment,
    ProjectContact,
    ProjectContactHistory,
    ProjectEstimate,
    ProjectEstimateHistory,
    ProjectLabel,
    ProjectLink,
    ProjectStatusHistory,
    ProjectTag,
    ProjectView,
)

logger = logging.getLogger(__name__)


class ProjectService:

    @staticmethod
    def list_projects(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {"name", "status", "priority"}

        from django.db.models import Exists, OuterRef
        from apps.onboarding.models import OnboardingRequest as _OnboardingRequest

        qs = (
            Project.objects.select_related(
                "project_type",
                "programme",
                "sub_status",
                "assigned_team",
            )
            .prefetch_related(
                "project_tags__tag",
                Prefetch(
                    "codes",
                    queryset=ProjectCode.objects.order_by("-created_at"),
                    to_attr="_prefetched_codes",
                ),
            )
            .annotate(
                via_onboarding=Exists(
                    _OnboardingRequest.objects.filter(project_id=OuterRef('pk'))
                )
            )
        )

        if filters:
            search = filters.get("search")
            if search:
                qs = qs.filter(
                    Q(name__icontains=search)
                    | Q(programme__name__icontains=search)
                    | Q(codes__code__icontains=search)
                    | Q(project_tags__tag__name__icontains=search)
                ).distinct()

            def _vals(key):
                raw = filters.get(key) or ""
                return [v.strip() for v in raw.split(",") if v.strip()]

            is_active_vals = _vals("is_active")
            if is_active_vals:
                bool_map = {"true": True, "false": False}
                bools = [bool_map[v] for v in is_active_vals if v in bool_map]
                if bools:
                    qs = qs.filter(is_active__in=bools)
            else:
                qs = qs.filter(is_active=True)

            status_vals = _vals("status")
            if status_vals:
                qs = qs.filter(status__in=status_vals)

            confidence_vals = _vals("confidence")
            if confidence_vals:
                qs = qs.filter(confidence__in=confidence_vals)

            priority_vals = _vals("priority")
            if priority_vals:
                qs = qs.filter(priority__in=priority_vals)

            project_type_vals = _vals("project_type")
            if project_type_vals:
                qs = qs.filter(project_type_id__in=project_type_vals)

            sub_status_vals = _vals("sub_status")
            if sub_status_vals:
                qs = qs.filter(sub_status_id__in=sub_status_vals)

            programme_vals = _vals("programme")
            if programme_vals:
                qs = qs.filter(programme_id__in=programme_vals)

            project_vals = _vals("project")
            if project_vals:
                qs = qs.filter(id__in=project_vals)

            team_vals = _vals("team")
            if team_vals:
                qs = qs.filter(
                    Q(assigned_team_id__in=team_vals)
                    | Q(project_collaborators__team_id__in=team_vals)
                ).distinct()

            tag_vals = _vals("tags")
            if tag_vals:
                qs = qs.filter(project_tags__tag_id__in=tag_vals).distinct()

        order_by = filters.get("order_by") if filters else None
        order_dir = filters.get("order_dir") if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else "name"
        if order_dir == "desc":
            order_field = f"-{order_field}"
        qs = qs.order_by(order_field)

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
    def list_stats(fields=None):
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = Project.objects.all()
        result = {}

        if wants("total_projects"):
            result["total_projects"] = qs.count()
        if wants("active_projects"):
            result["active_projects"] = qs.filter(is_active=True).count()
        if wants("inactive_projects"):
            result["inactive_projects"] = qs.filter(is_active=False).count()
        if wants("in_progress_projects"):
            result["in_progress_projects"] = qs.filter(
                status=Project.STATUS_IN_PROGRESS
            ).count()
        if wants("new_projects"):
            result["new_projects"] = qs.filter(status=Project.STATUS_NEW).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        result = {}

        if wants("status"):
            result["status"] = [
                {"value": k, "label": v} for k, v in Project.STATUS_CHOICES
            ]

        if wants("confidence"):
            result["confidence"] = [
                {"value": k, "label": v} for k, v in Project.CONFIDENCE_CHOICES
            ]

        if wants("priority"):
            result["priority"] = [
                {"value": k, "label": v} for k, v in Project.PRIORITY_CHOICES
            ]

        if wants("is_active"):
            result["is_active"] = [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]

        if wants("project_types"):
            from apps.project_types.models import ProjectType

            result["project_types"] = list(
                ProjectType.objects.filter(is_active=True)
                .values("id", "name")
                .order_by("name")
            )

        if wants("programmes"):
            from apps.programmes.models import Programme

            result["programmes"] = list(
                Programme.objects.filter(is_active=True)
                .values("id", "name")
                .order_by("name")
            )

        if wants("projects"):
            result["projects"] = list(
                Project.objects.filter(is_active=True)
                .annotate(programme_name=F("programme__name"))
                .values("id", "name", "programme_name")
                .order_by("name")
            )

        if wants("sub_statuses"):
            from apps.project_sub_statuses.models import ProjectSubStatus

            result["sub_statuses"] = list(
                ProjectSubStatus.objects.filter(is_active=True)
                .values("id", "name", "main_status")
                .order_by("name")
            )

        if wants("delivery_teams"):
            from apps.delivery_teams.models import DeliveryTeam

            result["delivery_teams"] = list(
                DeliveryTeam.objects.filter(is_active=True)
                .values("id", "name")
                .order_by("name")
            )

        if wants("tags"):
            from apps.tags.models import Tag

            result["tags"] = Tag.objects.values("id", "name").order_by("name")

        return result

    @staticmethod
    def get_project(project_id: int):
        if not project_id:
            raise ValidationError("Invalid: project_id must be a positive integer.")

        return Project.objects.select_related(
            "project_type", "programme", "sub_status", "assigned_team"
        ).get(pk=project_id)

    @staticmethod
    def get_project_with_teams(project_id: int):
        if not project_id:
            raise ValidationError("Invalid: project_id must be a positive integer.")

        return (
            Project.objects.select_related(
                "project_type", "programme", "sub_status", "assigned_team"
            )
            .prefetch_related("project_collaborators__team")
            .get(pk=project_id)
        )

    @staticmethod
    def _enforce_in_progress_rules(status: str, code: str, assigned_team_id):
        if status != Project.STATUS_IN_PROGRESS:
            return
        errors = {}
        if not (code or "").strip():
            errors["code"] = "Code is required when status is In Progress."
        if not assigned_team_id:
            errors["assigned_team"] = (
                "Assigned team is required when status is In Progress."
            )
        if errors:
            raise ValidationError(errors)

    @staticmethod
    @transaction.atomic
    def set_collaborators(project_id: int, team_ids: list):
        project = Project.objects.select_related("assigned_team").get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        assigned_id = project.assigned_team_id

        invalid = [tid for tid in team_ids if tid == assigned_id]
        if invalid:
            raise ValidationError("The assigned team cannot also be a collaborator.")

        existing_ids = set(
            ProjectCollaborator.objects.filter(project=project).values_list(
                "team_id", flat=True
            )
        )
        new_ids = set(team_ids)

        to_remove = existing_ids - new_ids
        to_add = new_ids - existing_ids

        ProjectCollaborator.objects.filter(
            project=project, team_id__in=to_remove
        ).delete()

        for team_id in to_add:
            try:
                pc = ProjectCollaborator(project=project, team_id=team_id)
                pc.full_clean()
                pc.save()
            except DatabaseError as e:
                logger.exception(
                    "DatabaseError setting collaborators '%s': %s", project_id, e
                )
                raise RuntimeError(
                    "A database error occurred. Please try again later."
                ) from e
            except Exception as e:
                logger.exception(
                    "Unexpected error when setting collaborators '%s': %s",
                    project_id,
                    e,
                )
                raise

        return project

    @staticmethod
    @transaction.atomic
    def add_collaborator(project_id: int, team_id: int):
        project = Project.objects.select_related("assigned_team").get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        if team_id == project.assigned_team_id:
            raise ValidationError("The assigned team cannot also be a collaborator.")

        if ProjectCollaborator.objects.filter(
            project=project, team_id=team_id
        ).exists():
            raise ValidationError("This team is already a collaborator.")

        try:
            pc = ProjectCollaborator(project=project, team_id=team_id)
            pc.full_clean()
            pc.save()
            return pc
        except DatabaseError as e:
            logger.exception(
                "DatabaseError adding collaborators '%s': %s", project_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when adding collaborators '%s': %s",
                project_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def remove_collaborator(project_id: int, team_id: int):
        deleted, _ = ProjectCollaborator.objects.filter(
            project_id=project_id, team_id=team_id
        ).delete()
        if not deleted:
            raise ValidationError("This team is not a collaborator on the project.")

    @staticmethod
    def _pk(value):
        if value is None:
            return None
        return value.pk if hasattr(value, "pk") else value

    @staticmethod
    def _resolve_programme(programme_value):
        from apps.programmes.models import Programme

        if not programme_value:
            # Default to "Others"
            try:
                return Programme.objects.get(name="Others")
            except Programme.DoesNotExist:
                return None

        # Already a model instance
        if hasattr(programme_value, "pk"):
            return programme_value

        # Numeric id
        try:
            pk = int(programme_value)
            try:
                return Programme.objects.get(pk=pk)
            except Programme.DoesNotExist:
                raise ValidationError(f"Programme with id {pk} does not exist.")
        except (TypeError, ValueError):
            pass

        # Name string — get or create
        name = str(programme_value).strip()
        if not name:
            try:
                return Programme.objects.get(name="Others")
            except Programme.DoesNotExist:
                return None

        programme, _ = Programme.objects.get_or_create(
            name__iexact=name,
            defaults={"name": name, "is_active": True},
        )
        return programme

    @staticmethod
    @transaction.atomic
    def create_project(data: dict, code: str = ""):
        if not isinstance(data, dict) or "name" not in data:
            raise ValidationError("Invalid: data must be a dict containing 'name'.")

        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")

        if Project.objects.filter(name=name).exists():
            raise ValidationError(f"Project '{name}' already exists.")

        raw_project_type = data.get("project_type")
        project_type_id = ProjectService._pk(raw_project_type)
        if not project_type_id:
            raise ValidationError("'project_type' is required.")

        programme = ProjectService._resolve_programme(data.get("programme"))
        programme_id = programme.pk if programme else None

        sub_status_id = ProjectService._pk(data.get("sub_status"))
        assigned_team_id = ProjectService._pk(data.get("assigned_team"))
        status = data.get("status") or Project.STATUS_NEW

        ProjectService._enforce_in_progress_rules(status, code, assigned_team_id)

        try:
            project = Project(
                name=name,
                project_type_id=project_type_id,
                programme_id=programme_id,
                status=status,
                sub_status_id=sub_status_id,
                assigned_team_id=assigned_team_id,
                confidence=data.get("confidence") or "",
                priority=data.get("priority") or "",
                tentative_start_date=data.get("tentative_start_date") or None,
                tentative_end_date=data.get("tentative_end_date") or None,
                is_active=data.get("is_active", True),
            )
            project.full_clean()
            project.save()

            ProjectLabelService.create_label(project)
            if code:
                ProjectCodeService.set_code(project.pk, code)
            ProjectStatusHistoryService.record_creation(project)
            return project
        except IntegrityError as e:
            logger.error("IntegrityError creating project '%s': %s", name, e)
            raise ValidationError(
                f"Project '{name}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating project '%s': %s", name, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error when creating project '%s': %s", name, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_project(project_id: int, data: dict, operational_only: bool = False):
        if not project_id:
            raise ValidationError("Invalid: project_id must be a positive integer.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        old_status = Project.objects.get(pk=project_id).status
        old_sub_status = (
            Project.objects.get(pk=project_id).sub_status
            if hasattr(project, "sub_status")
            else None
        )

        if operational_only:
            # Only update operational fields
            if "efforts_issued" in data:
                project.efforts_issued = data["efforts_issued"]
            if "effort_issue_commitment_date" in data:
                project.effort_issue_commitment_date = (
                    data.get("effort_issue_commitment_date") or None
                )
            if "run_cost_applies" in data:
                project.run_cost_applies = data["run_cost_applies"]
        else:
            # General fields
            if "name" in data:
                new_name = (data["name"] or "").strip()
                if not new_name:
                    raise ValidationError("'name' cannot be blank.")
                if (
                    Project.objects.filter(name=new_name)
                    .exclude(pk=project_id)
                    .exists()
                ):
                    raise ValidationError(f"Project '{new_name}' already exists.")
                project.name = new_name

            if "project_type" in data:
                project.project_type_id = ProjectService._pk(data["project_type"])

            if "programme" in data:
                programme = ProjectService._resolve_programme(data.get("programme"))
                project.programme_id = programme.pk if programme else None

            if "code" in data:
                project.code = (data.get("code") or "").strip()

            if "status" in data:
                project.status = data["status"]

            if "sub_status" in data:
                project.sub_status_id = (
                    ProjectService._pk(data.get("sub_status")) or None
                )

            if "assigned_team" in data:
                project.assigned_team_id = (
                    ProjectService._pk(data.get("assigned_team")) or None
                )

            if "confidence" in data:
                project.confidence = data.get("confidence") or ""

            if "priority" in data:
                project.priority = data.get("priority") or ""

            if "tentative_start_date" in data:
                project.tentative_start_date = data.get("tentative_start_date") or None

            if "tentative_end_date" in data:
                project.tentative_end_date = data.get("tentative_end_date") or None

            if "is_active" in data:
                project.is_active = data["is_active"]

            ProjectService._enforce_in_progress_rules(
                project.status,
                project.code,
                project.assigned_team_id,
            )

        try:
            project.full_clean()
            project.save()

            if project.status != old_status or project.sub_status != old_sub_status:
                ProjectStatusHistoryService.record_transition(
                    project=project,
                    previous_status=old_status,
                    new_status=project.status,
                    previous_sub_status=old_sub_status,
                    new_sub_status=(
                        project.sub_status if hasattr(project, "sub_status") else None
                    ),
                    reason=data.get("reason") or None,
                )

            return project
        except IntegrityError as e:
            logger.error("IntegrityError updating project %s: %s", project_id, e)
            raise ValidationError(
                "Project could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating project %s: %s", project_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating project '%s': %s", project_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_project_teams(project_id: int, data: dict):
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        project = Project.objects.select_related("assigned_team").get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        if "assigned_team" in data:
            try:
                new_assigned_id = ProjectService._pk(data.get("assigned_team")) or None
                project.assigned_team_id = new_assigned_id
                project.full_clean()
                project.save(update_fields=["assigned_team", "updated_at"])
            except DatabaseError as e:
                logger.exception(
                    "DatabaseError updating project teams %s: %s", project_id, e
                )
                raise RuntimeError(
                    "A database error occurred. Please try again later."
                ) from e
            except Exception as e:
                logger.exception(
                    "Unexpected error when updating project teams '%s': %s",
                    project_id,
                    e,
                )
                raise

        if "collaborator_ids" in data:
            collaborator_ids = [int(i) for i in (data["collaborator_ids"] or [])]
            project.refresh_from_db(fields=["assigned_team"])
            ProjectService.set_collaborators(project_id, collaborator_ids)

        return ProjectService.get_project_with_teams(project_id)

    @staticmethod
    @transaction.atomic
    def delete_project(project_id: int):
        if not project_id:
            raise ValidationError("Invalid: project_id must be a positive integer.")

        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        try:
            project.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting project %s: %s", project_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting project '%s': %s", project_id, e
            )
            raise


class ProjectLabelService:
    @staticmethod
    def suggest_label(project: Project):
        """
        Return a suggested label string for *project*.

        When AI_ENABLED=true, delegates to ProjectLabelAI which calls the
        configured provider and falls back here on any failure.
        When AI_ENABLED=false, runs the deterministic engine directly.
        """
        from apps.configurations.services import ConfigurationService

        ai_enabled = ConfigurationService.get_bool("AI_ENABLED", False)

        if ai_enabled:
            from .ai import ProjectLabelAI

            return ProjectLabelAI.suggest(project)

        return ProjectLabelService._suggest_deterministic(project)

    @staticmethod
    def _suggest_deterministic(project: Project):
        """
        Rule-based label generation — the original logic, preserved here
        as the canonical deterministic implementation.  Called directly
        when AI is disabled, and by ProjectLabelAI as its fallback.
        """
        programme_name = None
        if hasattr(project, "programme") and project.programme:
            programme_name = project.programme.name

        candidates = ProjectLabelEngineService.build_candidates(
            programme_name, project.name
        )
        for candidate in candidates:
            if not ProjectLabel.objects.filter(label=candidate).exists():
                return candidate

        # All natural patterns taken — suffix the first (shortest) candidate
        base = (
            candidates[0]
            if candidates
            else re.sub(r"[^A-Z0-9_]", "", project.name.upper())[:30]
        )
        return ProjectLabelEngineService.resolve_collision(base)

    @staticmethod
    def list_labels_for_project(project: Project, page: int = 1, page_size: int = 20):
        qs = ProjectLabel.objects.filter(project=project).order_by(
            "-is_primary", "label"
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
    def get_label(project: Project, label_id: int):
        return ProjectLabel.objects.get(pk=label_id, project=project)

    @staticmethod
    @transaction.atomic
    def create_label(
        project: Project, label: str | None = None, is_primary: bool = False
    ):
        if label:
            label = label.strip().upper()
        else:
            label = ProjectLabelService.suggest_label(project)

        if not re.match(r"^[A-Z0-9_]+$", label):
            raise ValueError(
                "Label must contain only uppercase letters, digits, and underscores."
            )

        if ProjectLabel.objects.filter(label=label).exclude(project=project).exists():
            raise ValueError(f"Label '{label}' is already in use by another project.")

        existing_count = ProjectLabel.objects.filter(project=project).count()
        if existing_count == 0:
            is_primary = True

        if is_primary:
            ProjectLabel.objects.filter(project=project, is_primary=True).update(
                is_primary=False
            )

        try:
            return ProjectLabel.objects.create(
                project=project, label=label, is_primary=is_primary
            )
        except IntegrityError as e:
            logger.error("IntegrityError creating label '%s': %s", label, e)
            raise ValidationError(
                f"Label '{label}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating label '%s': %s", label, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error when creating label '%s': %s", label, e)
            raise

    @staticmethod
    @transaction.atomic
    def update_label(project: Project, label_id: int, **kwargs):
        lbl = ProjectLabel.objects.select_for_update().get(pk=label_id, project=project)

        if "label" in kwargs and kwargs["label"]:
            new_val = kwargs["label"].strip().upper()
            if not re.match(r"^[A-Z0-9_]+$", new_val):
                raise ValueError(
                    "Label must contain only uppercase letters, digits, and underscores."
                )

            if ProjectLabel.objects.filter(label=new_val).exclude(pk=lbl.pk).exists():
                raise ValueError(f"Label '{new_val}' is already in use.")

            lbl.label = new_val

        is_primary = kwargs.get("is_primary")

        try:
            if is_primary is True:
                ProjectLabel.objects.filter(project=project, is_primary=True).exclude(
                    pk=lbl.pk
                ).update(is_primary=False)
                lbl.is_primary = True
            elif is_primary is False:
                lbl.is_primary = False
                replacement = (
                    ProjectLabel.objects.filter(project=project)
                    .exclude(pk=lbl.pk)
                    .order_by("-created_at")
                    .first()
                )
                if replacement:
                    replacement.is_primary = True
                    replacement.save(update_fields=["is_primary"])

            lbl.save()
            return lbl
        except IntegrityError as e:
            logger.error("IntegrityError updating label %s: %s", label_id, e)
            raise ValidationError(
                "Label could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating label %s: %s", label_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating label '%s': %s", label_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_label(project: Project, label_id: int):
        lbl = ProjectLabel.objects.get(pk=label_id, project=project)

        try:
            if lbl.is_primary:
                next_lbl = (
                    ProjectLabel.objects.filter(project=project)
                    .exclude(pk=lbl.pk)
                    .order_by("created_at")
                    .first()
                )

                if next_lbl:
                    next_lbl.is_primary = True
                    next_lbl.save(update_fields=["is_primary"])
            lbl.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting label %s: %s", label_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting label '%s': %s", label_id, e
            )
            raise


class ProjectStatusHistoryService:
    @staticmethod
    def record_creation(project: Project):
        try:
            return ProjectStatusHistory.objects.create(
                project=project,
                previous_status="",
                new_status=project.status,
                previous_sub_status=None,
                new_sub_status=(
                    project.sub_status if hasattr(project, "sub_status") else None
                ),
                reason=None,
            )
        except IntegrityError as e:
            logger.error(
                "IntegrityError creating project status history '%s': %s", project.pk, e
            )
            raise ValidationError(
                f"Project status history '{project.pk}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError creating project status history '%s': %s", project.pk, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating project status history '%s': %s",
                project.pk,
                e,
            )
            raise

    @staticmethod
    def record_transition(
        project: Project,
        previous_status: str,
        new_status: str,
        previous_sub_status=None,
        new_sub_status=None,
        reason: str | None = None,
    ):
        try:
            return ProjectStatusHistory.objects.create(
                project=project,
                previous_status=previous_status,
                new_status=new_status,
                previous_sub_status=previous_sub_status,
                new_sub_status=new_sub_status,
                reason=reason or None,
            )
        except IntegrityError as e:
            logger.error(
                "IntegrityError updating project status history %s: %s", project.pk, e
            )
            raise ValidationError(
                "Project status history could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError updating proproject status historyject %s: %s",
                project.pk,
                e,
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating project status history '%s': %s",
                project.pk,
                e,
            )
            raise

    @staticmethod
    def list_history_for_project(project: Project, page: int = 1, page_size: int = 20):
        qs = (
            ProjectStatusHistory.objects.filter(project=project)
            .select_related("previous_sub_status", "new_sub_status")
            .order_by("-created_at")
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


class ProjectTagService:
    MAX_TAGS = 10

    @staticmethod
    def list_tags_for_project(project_id: int):
        return (
            ProjectTag.objects.filter(project_id=project_id)
            .select_related("tag")
            .order_by("tag__name")
        )

    @staticmethod
    @transaction.atomic
    def add_tag(project_id: int, name: str):
        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        current_count = ProjectTag.objects.filter(project=project).count()
        if current_count >= ProjectTagService.MAX_TAGS:
            raise ValidationError(
                {
                    "name": f"A project can have at most {ProjectTagService.MAX_TAGS} tags."
                }
            )

        tag = TagService.get_or_create(name)

        try:
            return ProjectTag.objects.get_or_create(project=project, tag=tag)
        except (IntegrityError, DatabaseError):
            if ProjectTag.objects.filter(project=project, tag=tag).exists():
                raise ValidationError(
                    {"name": "This tag is already applied to the project."}
                )

            logger.exception("Error linking tag '%s' to project %s", name, project_id)
            raise RuntimeError("A database error occurred. Please try again later.")

    @staticmethod
    @transaction.atomic
    def remove_tag(project_id: int, tag_id: int):
        pt = ProjectTag.objects.filter(project_id=project_id, tag_id=tag_id).first()
        if not pt:
            raise ValidationError("Tag not found on this project.")

        try:
            tag = pt.tag
            pt.delete()
            TagService.delete_if_orphan(tag)
        except DatabaseError as e:
            logger.exception("DatabaseError deleting tag %s: %s", tag_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception("Unexpected error when deleting tag '%s': %s", tag_id, e)
            raise


class ProjectCommentService:
    MAX_PINNED = 3

    @staticmethod
    def list_for_project(project_id: int, page=1, page_size=20):
        pinned = list(
            ProjectComment.objects.filter(
                project_id=project_id, is_pinned=True
            ).order_by("-created_at")
        )
        non_pinned_qs = ProjectComment.objects.filter(
            project_id=project_id, is_pinned=False
        ).order_by("-created_at")

        paginator = Paginator(non_pinned_qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "pinned": pinned,
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
    def create_comment(project_id: int, comment_text: str, user=None):
        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        if not comment_text or not comment_text.strip():
            raise ValidationError({"comment": "Comment cannot be blank."})

        posted_by = 'Anonymous'
        if user and user.is_authenticated:
            posted_by = user.get_full_name() or user.email or 'Anonymous'

        try:
            comment = ProjectComment.objects.create(
                project=project,
                comment=comment_text,
                posted_by=posted_by,
                posted_by_user=user if (user and user.is_authenticated) else None,
            )
            # Extract & persist @mentions, then send in-app notifications
            mentioned_ids = ProjectCommentService._extract_mention_ids(comment_text)
            if mentioned_ids:
                comment.mentioned_users.set(mentioned_ids)
                try:
                    from django.contrib.auth import get_user_model
                    from apps.notifications.services import NotificationService
                    from apps.notifications.models import Notification
                    User = get_user_model()
                    mentioned_users = User.objects.filter(pk__in=mentioned_ids, is_active=True)
                    project_link = f'/projects/{project.pk}/'
                    for mu in mentioned_users:
                        if user and mu.pk == user.pk:
                            continue
                        NotificationService.create(
                            mu,
                            title=f'{posted_by} mentioned you in a comment on {project.name}',
                            notification_type=Notification.TYPE_COMMENT_MENTION,
                            link=project_link,
                        )
                except Exception:
                    logger.exception("Failed to create mention notifications for comment %s", comment.pk)
            # Notify project followers (excluding the commenter)
            try:
                from apps.notifications.services import NotificationService
                from apps.notifications.models import Notification
                from .models import ProjectFollower
                follower_ids = list(
                    ProjectFollower.objects.filter(project=project)
                    .exclude(user=user)
                    .values_list('user_id', flat=True)
                ) if user and user.is_authenticated else list(
                    ProjectFollower.objects.filter(project=project)
                    .values_list('user_id', flat=True)
                )
                if follower_ids:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    for fu in User.objects.filter(pk__in=follower_ids, is_active=True):
                        NotificationService.create(
                            fu,
                            title=f'New comment on {project.name}',
                            notification_type=Notification.TYPE_PROJECT_FOLLOW,
                            body=f'by {posted_by}',
                            link=f'/projects/{project.pk}/',
                        )
            except Exception:
                logger.exception("Failed to create follow notifications for comment %s", comment.pk)
            return comment
        except IntegrityError as e:
            logger.error("IntegrityError creating comment '%s': %s", project_id, e)
            raise ValidationError(
                f"Comment for project '{project_id}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating comment '%s': %s", project_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating comment '%s': %s", project_id, e
            )
            raise

    @staticmethod
    def _extract_mention_ids(html: str) -> list[int]:
        """Parse data-user-id attributes from @mention spans in HTML comment bodies."""
        import re
        return [int(m) for m in re.findall(r'data-user-id=["\'](\d+)["\']', html)]

    @staticmethod
    @transaction.atomic
    def update_comment(comment_id: int, data: dict):
        comment = ProjectComment.objects.get(pk=comment_id)
        if not comment:
            raise ValidationError(f"Comment '{comment_id}' does not exist.")

        if "comment" in data:
            new_text = (data["comment"] or "").strip()
            if not new_text:
                raise ValidationError({"comment": "Comment cannot be blank."})
            comment.comment = new_text
            comment.is_edited = True

        if "is_pinned" in data:
            new_pinned = bool(data["is_pinned"])
            if new_pinned and not comment.is_pinned:
                current_pinned = ProjectComment.objects.filter(
                    project=comment.project, is_pinned=True
                ).count()
                if current_pinned >= ProjectCommentService.MAX_PINNED:
                    raise ValidationError(
                        {
                            "is_pinned": f"Maximum {ProjectCommentService.MAX_PINNED} pinned comments allowed per project."
                        }
                    )
            comment.is_pinned = new_pinned

        try:
            comment.save()
            return comment
        except IntegrityError as e:
            logger.error("IntegrityError updating comment %s: %s", comment_id, e)
            raise ValidationError(
                "Project comment could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating comment %s: %s", comment_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating comment '%s': %s", comment_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_comment(comment_id: int):
        try:
            ProjectComment.objects.filter(pk=comment_id).delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting comment %s: %s", comment_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting comment '%s': %s", comment_id, e
            )
            raise


class ProjectCodeService:
    @staticmethod
    def get_active(project_id: int):
        return (
            ProjectCode.objects.filter(project_id=project_id)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def get_history(project_id: int, page: int = 1, page_size: int = 20):
        qs = ProjectCode.objects.filter(project_id=project_id).order_by("-created_at")
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
    def set_code(project_id: int, code: str, notes: str | None = None):
        code = code.strip()
        if not code:
            raise ValueError("code is required")

        return ProjectCode.objects.create(
            project_id=project_id,
            code=code,
            notes=notes or None,
        )


class ProjectEstimateService:
    IMMUTABLE_AFTER_APPROVED = {
        "estimate_days",
        "contingency_pct",
        "estimate_link",
        "shared_by",
        "reviewed_by",
    }

    @staticmethod
    def list_estimates(project_id: int, page=1, page_size=20):
        qs = (
            ProjectEstimate.objects.filter(project_id=project_id)
            .select_related("project")
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
    def get_estimate(project_id: int, estimate_id: int):
        return ProjectEstimate.objects.select_related("project").get(
            pk=estimate_id, project_id=project_id
        )

    @staticmethod
    def _supersede_previous(approved_estimate, project):
        previous = (
            ProjectEstimate.objects.filter(
                project=project,
                status=ProjectEstimate.STATUS_APPROVED,
            )
            .exclude(pk=approved_estimate.pk)
            .first()
        )
        if previous:
            old_status = previous.status
            previous.status = ProjectEstimate.STATUS_SUPERSEDED
            previous.save(update_fields=["status", "updated_at"])
            ProjectEstimateHistory.objects.create(
                estimate=previous,
                project=project,
                action=ProjectEstimateHistory.ACTION_SUPERSEDED,
                previous_status=old_status,
                new_status=ProjectEstimate.STATUS_SUPERSEDED,
                notes=None,
            )

    @staticmethod
    @transaction.atomic
    def create_estimate(project_id: int, data: dict, notes: str = ""):
        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        estimate_days = data.get("estimate_days")
        if not estimate_days:
            raise ValidationError("Invalid: estimate_days cannot be blank.")
        else:
            estimate_days = Decimal(str(estimate_days))

        contingency_pct = Decimal(str(data.get("contingency_pct")) or "0")

        # auto-increment version per project
        last = (
            ProjectEstimate.objects.filter(project=project)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        next_version = (last or 0) + 1

        # snapshot day rate
        from apps.configurations.services import ConfigurationService

        day_rate = ConfigurationService.get_float("SPRINT_POINT_PRICE", fallback=0.0)

        status = data.get("status") or ProjectEstimate.STATUS_DRAFT
        if status == ProjectEstimate.STATUS_SUPERSEDED:
            raise ValueError("Cannot create an estimate with status SUPERSEDED.")

        try:
            estimate = ProjectEstimate.objects.create(
                project=project,
                version=next_version,
                estimate_link=data.get("estimate_link") or None,
                shared_by=data.get("shared_by") or "",
                reviewed_by=data.get("reviewed_by") or "",
                status=status,
                estimate_days=estimate_days,
                contingency_pct=contingency_pct,
                day_rate=Decimal(str(day_rate)),
            )

            ProjectEstimateHistory.objects.create(
                estimate=estimate,
                project=project,
                action=ProjectEstimateHistory.ACTION_CREATED,
                previous_status="",
                new_status=status,
                notes=notes or None,
            )

            if status == ProjectEstimate.STATUS_APPROVED:
                ProjectEstimateService._supersede_previous(estimate, project)

            return estimate
        except IntegrityError as e:
            logger.error(
                "IntegrityError creating project estimate '%s': %s", project_id, e
            )
            raise ValidationError(
                f"Project estimate for project '{project_id}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError creating project estimate '%s': %s", project_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating project estimate '%s': %s",
                project_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_estimate(project_id: int, estimate_id: int, data: dict, notes: str = ""):
        estimate = ProjectEstimate.objects.select_for_update().get(
            pk=estimate_id, project_id=project_id
        )

        if estimate.status == ProjectEstimate.STATUS_APPROVED:
            raise ValueError("Approved estimates are immutable. Create a new version.")
        if estimate.status == ProjectEstimate.STATUS_SUPERSEDED:
            raise ValueError("Superseded estimates cannot be modified.")

        previous_status = estimate.status
        changed = False

        new_status = data.get("status")
        if new_status and new_status != previous_status:
            if new_status == ProjectEstimate.STATUS_SUPERSEDED:
                raise ValueError("Cannot manually set status to SUPERSEDED.")
            estimate.status = new_status
            changed = True

        # non-status fields — only allowed in DRAFT
        mutable_fields = {
            "estimate_link": lambda v: v or None,
            "shared_by": lambda v: v or "",
            "reviewed_by": lambda v: v or "",
            "estimate_days": lambda v: Decimal(str(v)),
            "contingency_pct": lambda v: Decimal(str(v or "0")),
        }

        for field, coerce in mutable_fields.items():
            if field in data:
                if (
                    field in ("estimate_days", "contingency_pct")
                    and previous_status != ProjectEstimate.STATUS_DRAFT
                ):
                    raise ValueError(f"'{field}' can only be changed in DRAFT status.")
                setattr(estimate, field, coerce(data[field]))
                changed = True

        try:
            if changed:
                estimate.save()

                action = ProjectEstimateHistory.ACTION_UPDATED
                if estimate.status == ProjectEstimate.STATUS_APPROVED:
                    action = ProjectEstimateHistory.ACTION_APPROVED

                ProjectEstimateHistory.objects.create(
                    estimate=estimate,
                    project_id=project_id,
                    action=action,
                    previous_status=previous_status,
                    new_status=estimate.status,
                    notes=notes or None,
                )

                if estimate.status == ProjectEstimate.STATUS_APPROVED:
                    ProjectEstimateService._supersede_previous(
                        estimate, estimate.project
                    )

            return estimate
        except IntegrityError as e:
            logger.error(
                "IntegrityError updating project estimate %s: %s", estimate_id, e
            )
            raise ValidationError(
                "Project could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError updating project estimate %s: %s", estimate_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating project estimate '%s': %s",
                estimate_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_estimate(project_id: int, estimate_id: int):
        estimate = ProjectEstimate.objects.get(pk=estimate_id, project_id=project_id)
        if estimate.status == ProjectEstimate.STATUS_APPROVED:
            raise ValueError("Approved estimates cannot be deleted.")

        try:
            estimate.delete()
        except DatabaseError as e:
            logger.exception(
                "DatabaseError deleting project estimate %s: %s", estimate_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting project estimate '%s': %s",
                estimate_id,
                e,
            )
            raise

    @staticmethod
    def list_options(project_id: int, fields=None):
        def wants(field):
            return fields is None or field in fields

        result = {}

        if wants("status"):
            result["status"] = [
                {"value": value, "label": label}
                for value, label in ProjectEstimate.STATUS_CHOICES
                if value != ProjectEstimate.STATUS_SUPERSEDED
            ]

        if wants("versions"):
            result["versions"] = list(
                ProjectEstimate.objects.filter(project_id=project_id)
                .annotate(
                    version_label=Concat(
                        Value("v"), "version", output_field=CharField()
                    )
                )
                .values("id", "version", "version_label", "status")
                .order_by("-version")
            )

        if wants("tshirt_sizes"):
            result["tshirt_sizes"] = get_tshirt_size_definitions()

        return result

    @staticmethod
    def list_history(project_id: int, estimate_id: int, page=1, page_size=20):
        qs = ProjectEstimateHistory.objects.filter(
            estimate_id=estimate_id, project_id=project_id
        ).order_by("-created_at")

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


class ProjectBudgetService:
    @staticmethod
    def _threshold_pct():
        from apps.configurations.services import ConfigurationService

        return Decimal(
            str(ConfigurationService.get_float("BUDGET_THRESHOLD_PCT", fallback=10.0))
        )

    @staticmethod
    def _green_pct_for_size(size):
        from apps.configurations.services import ConfigurationService

        defaults = {"XS": "0.25", "S": "0.50", "M": "1.00", "L": "1.00", "XL": "1.00"}
        key = f"BUDGET_SIZE_{size}_GREEN_PCT"
        return Decimal(
            str(
                ConfigurationService.get_float(
                    key, fallback=float(defaults.get(size, "1.00"))
                )
            )
        )

    @staticmethod
    def _risk(actual_budget, estimate_total_cost):
        """
        Returns (risk, display, short, signed_risk_pct)
        """
        if actual_budget is None or estimate_total_cost is None:
            return None, None, None, None

        try:
            actual_budget = Decimal(str(actual_budget))
            estimate_total_cost = Decimal(str(estimate_total_cost))
        except (InvalidOperation, TypeError):
            return None, None, None, None

        if actual_budget == 0 or estimate_total_cost == 0:
            return None, None, None, None

        threshold = ProjectBudgetService._threshold_pct()
        size = get_tshirt_size(actual_budget)
        green_pct = ProjectBudgetService._green_pct_for_size(size)
        variance_pct = (estimate_total_cost - actual_budget) / actual_budget * 100
        sign = "+" if variance_pct >= 0 else ""
        risk_pct_str = f"{sign}{variance_pct:.2f}"
        abs_variance = abs(variance_pct)

        if abs_variance <= green_pct:
            return "GREEN", "On Budget", "OB", risk_pct_str
        elif abs_variance <= threshold:
            if variance_pct > 0:
                return "AMBER", "At Risk (Over)", "AR+", risk_pct_str
            else:
                return "AMBER", "At Risk (Under)", "AR-", risk_pct_str
        else:
            if variance_pct > 0:
                return "RED", "Over Budget", "OVR", risk_pct_str
            else:
                return "RED", "Under Budget", "UND", risk_pct_str

    @staticmethod
    def _enrich(budget):
        if budget is None:
            return None

        actual = budget.actual_budget
        cost = (
            Decimal(str(budget.estimate_version.total_cost))
            if budget.estimate_version
            else None
        )
        risk, risk_display, risk_short, risk_pct = ProjectBudgetService._risk(
            actual, cost
        )
        budget._actual_budget = actual
        budget._remaining_budget = budget.remaining_budget
        budget._budget_risk = risk
        budget._budget_risk_display = risk_display or "-"
        budget._budget_risk_short = risk_short or "-"
        budget._budget_risk_pct = risk_pct
        return budget

    @staticmethod
    def list_for_project(project_id):
        qs = (
            ProjectBudget.objects.filter(project_id=project_id)
            .select_related("financial_year", "estimate_version")
            .order_by("financial_year__start_date")
        )
        return [ProjectBudgetService._enrich(b) for b in qs]

    @staticmethod
    def get_budget(project_id, budget_id):
        budget = ProjectBudget.objects.select_related(
            "financial_year", "estimate_version"
        ).get(pk=budget_id, project_id=project_id)
        return ProjectBudgetService._enrich(budget)

    @staticmethod
    def list_history(project_id, budget_id, page=1, page_size=20):
        qs = ProjectBudgetHistory.objects.filter(
            budget_id=budget_id, project_id=project_id
        ).select_related(
            "financial_year", "previous_estimate_version", "new_estimate_version"
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
    def lifetime_budget(project_id):
        budgets = ProjectBudget.objects.filter(project_id=project_id).select_related(
            "financial_year", "estimate_version"
        )
        total_actual = Decimal("0")
        total_cost = Decimal("0")
        partial_budget_warning = False
        has_any = False

        for b in budgets:
            has_any = True
            actual = b.actual_budget
            if actual is None:
                partial_budget_warning = True
                continue
            total_actual += Decimal(str(actual))
            if b.estimate_version is not None:
                total_cost += Decimal(str(b.estimate_version.total_cost))

        remaining = (
            (total_actual - total_cost)
            if has_any and not partial_budget_warning
            else None
        )
        risk, risk_display, risk_short, risk_pct = ProjectBudgetService._risk(
            total_actual if has_any else None,
            total_cost if has_any else None,
        )

        return {
            "total_actual_budget": total_actual if has_any else None,
            "total_estimate_cost": total_cost,
            "remaining_budget": remaining,
            "budget_risk": risk,
            "budget_risk_display": risk_display or "-",
            "budget_risk_short": risk_short,
            "budget_risk_pct": risk_pct,
            "partial_budget_warning": partial_budget_warning,
        }

    @staticmethod
    @transaction.atomic
    def create_budget(
        project_id,
        financial_year_id,
        allocated_budget=None,
        refined_budget=None,
        estimate_version_id=None,
        notes=None,
    ):
        from apps.financial_years.models import FinancialYear

        project = Project.objects.get(pk=project_id)

        if not financial_year_id:
            raise ValidationError("Invalid: financial_year_id cannot be blank.")
        fy = FinancialYear.objects.get(pk=financial_year_id)

        try:
            budget = ProjectBudget.objects.create(
                project=project,
                financial_year=fy,
                allocated_budget=(
                    Decimal(str(allocated_budget))
                    if allocated_budget is not None
                    else None
                ),
                refined_budget=(
                    Decimal(str(refined_budget)) if refined_budget is not None else None
                ),
                estimate_version_id=estimate_version_id,
                notes=notes,
            )

            new_cost = (
                Decimal(str(budget.estimate_version.total_cost))
                if budget.estimate_version
                else None
            )

            ProjectBudgetHistory.objects.create(
                budget=budget,
                project=project,
                financial_year=fy,
                action=ProjectBudgetHistory.ACTION_CREATED,
                new_allocated_budget=budget.allocated_budget,
                new_refined_budget=budget.refined_budget,
                new_estimate_version_id=estimate_version_id,
                new_total_cost=new_cost,
            )

            return ProjectBudgetService._enrich(budget)
        except IntegrityError as e:
            logger.error(
                "IntegrityError creating project budget '%s': %s", project_id, e
            )
            raise ValidationError(
                f"Project budget for project '{project_id}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError creating project budget '%s': %s", project_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating project budget '%s': %s",
                project_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_budget(project_id, budget_id, **kwargs):
        budget = ProjectBudget.objects.select_related("estimate_version").get(
            pk=budget_id, project_id=project_id
        )

        tracked_keys = {"allocated_budget", "refined_budget", "estimate_version_id"}
        changed = bool(tracked_keys & kwargs.keys())

        prev_allocated = budget.allocated_budget
        prev_refined = budget.refined_budget
        prev_estimate_id = budget.estimate_version_id
        prev_cost = (
            Decimal(str(budget.estimate_version.total_cost))
            if budget.estimate_version
            else None
        )

        DECIMAL_FIELDS = {"allocated_budget", "refined_budget"}

        for field, value in kwargs.items():
            if field in DECIMAL_FIELDS and value is not None:
                try:
                    value = Decimal(str(value))
                except (InvalidOperation, TypeError):
                    raise ValueError(f"Invalid value for {field}: {value}")
            setattr(budget, field, value)

        try:
            budget.save()

            if changed:
                new_ev_id = budget.estimate_version_id
                try:
                    from apps.projects.models import ProjectEstimate

                    ev = (
                        ProjectEstimate.objects.get(pk=new_ev_id) if new_ev_id else None
                    )
                    new_cost = Decimal(str(ev.total_cost)) if ev else None
                except Exception:
                    new_cost = None

                ProjectBudgetHistory.objects.create(
                    budget=budget,
                    project_id=project_id,
                    financial_year=budget.financial_year,
                    action=ProjectBudgetHistory.ACTION_UPDATED,
                    previous_allocated_budget=prev_allocated,
                    previous_refined_budget=prev_refined,
                    previous_estimate_version_id=prev_estimate_id,
                    previous_total_cost=prev_cost,
                    new_allocated_budget=budget.allocated_budget,
                    new_refined_budget=budget.refined_budget,
                    new_estimate_version_id=budget.estimate_version_id,
                    new_total_cost=new_cost,
                )

            return ProjectBudgetService._enrich(budget)
        except IntegrityError as e:
            logger.error("IntegrityError updating project budget %s: %s", budget_id, e)
            raise ValidationError(
                "Project could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError updating project budget %s: %s", budget_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating project budget '%s': %s",
                budget_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_budget(project_id, budget_id):
        try:
            budget = ProjectBudget.objects.get(pk=budget_id, project_id=project_id)
            budget.delete()
        except DatabaseError as e:
            logger.exception(
                "DatabaseError deleting project budget %s: %s", budget_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting project budget '%s': %s",
                budget_id,
                e,
            )
            raise


class ProjectContactService:
    MAX_PER_ROLE = 10

    @staticmethod
    def list_for_project(project_id: int, role: str | None = None):
        qs = (
            ProjectContact.objects.filter(project_id=project_id)
            .select_related("contact")
            .order_by("role", "contact__name")
        )
        if role:
            qs = qs.filter(role=role)
        return list(qs)

    @staticmethod
    def list_active_for_project(project_id: int, role: str | None = None):
        qs = (
            ProjectContact.objects.filter(project_id=project_id, is_active=True)
            .select_related("contact")
            .order_by("role", "contact__name")
        )
        if role:
            qs = qs.filter(role=role)
        return list(qs)

    @staticmethod
    @transaction.atomic
    def add(
        project_id: int,
        role: str,
        contact_id: int | None = None,
        name: str = "",
        email: str = "",
    ) -> ProjectContact:
        """
        Add contact to project-role. contact_id takes priority.
        If not supplied, get_or_create from name+email.
        Raises ValueError on cap or duplicate active.
        """
        from apps.contacts.models import Contact
        from apps.contacts.services import ContactService

        project = Project.objects.get(pk=project_id)

        if contact_id:
            contact = Contact.objects.get(pk=contact_id)
        else:
            if not name or not email:
                raise ValueError(
                    "name and email required when contact_id not provided."
                )
            contact = ContactService.create_contact(
                {
                    "name": name,
                    "email": email,
                }
            )
            # contact, _ = ContactService.get_or_create(name, email)

        if not contact.is_active:
            raise ValueError("Contact is inactive. Reactivate before assigning.")

        # max cap per role
        active_count = ProjectContact.objects.filter(
            project=project, role=role, is_active=True
        ).count()
        if active_count >= ProjectContactService.MAX_PER_ROLE:
            raise ValueError(
                f"Max {ProjectContactService.MAX_PER_ROLE} contacts per role reached."
            )

        # unique_together — may already exist (inactive → reactivate row)
        pc, created = ProjectContact.objects.get_or_create(
            project=project,
            contact=contact,
            role=role,
            defaults={"is_active": True},
        )
        if not created:
            if pc.is_active:
                raise ValueError("Contact already active in this role.")
            pc.is_active = True
            pc.save(update_fields=["is_active", "updated_at"])

        ProjectContactHistory.objects.create(
            project=project,
            contact=contact,
            role=role,
            action=ProjectContactHistory.ACTION_ADDED,
        )
        return pc

    @staticmethod
    @transaction.atomic
    def remove(
        project_contact_id: int,
        reason: str = "",
    ) -> ProjectContact:
        pc = ProjectContact.objects.select_related("contact", "project").get(
            pk=project_contact_id
        )
        if not pc.is_active:
            raise ValueError("Already inactive.")
        pc.is_active = False
        pc.save(update_fields=["is_active", "updated_at"])
        ProjectContactHistory.objects.create(
            project=pc.project,
            contact=pc.contact,
            role=pc.role,
            action=ProjectContactHistory.ACTION_REMOVED,
            reason=reason or "",
        )
        return pc

    @staticmethod
    def history(project_id: int) -> list[ProjectContactHistory]:
        return list(
            ProjectContactHistory.objects.filter(project_id=project_id)
            .select_related("contact")
            .order_by("-created_at")
        )

    @staticmethod
    def get(project_contact_id: int) -> ProjectContact:
        return ProjectContact.objects.select_related("contact", "project").get(
            pk=project_contact_id
        )

    @staticmethod
    @transaction.atomic
    def archive(project_contact_id: int, reason: str = "") -> ProjectContact:
        return ProjectContactService.remove(project_contact_id, reason)

    @staticmethod
    @transaction.atomic
    def unarchive(project_contact_id: int) -> ProjectContact:
        pc = ProjectContact.objects.select_related("contact", "project").get(
            pk=project_contact_id
        )
        if pc.is_active:
            raise ValueError("Already active.")
        if not pc.contact.is_active:
            raise ValueError("Contact is inactive in pool. Reactivate contact first.")

        active_count = ProjectContact.objects.filter(
            project=pc.project, role=pc.role, is_active=True
        ).count()
        if active_count >= ProjectContactService.MAX_PER_ROLE:
            raise ValueError(
                f"Max {ProjectContactService.MAX_PER_ROLE} contacts per role reached."
            )

        pc.is_active = True
        pc.save(update_fields=["is_active", "updated_at"])
        ProjectContactHistory.objects.create(
            project=pc.project,
            contact=pc.contact,
            role=pc.role,
            action=ProjectContactHistory.ACTION_ADDED,
        )
        return pc

    # ── contact detail page helpers ────────────────────────────────────────────

    @staticmethod
    def assignments_for_contact(contact_id: int) -> list[ProjectContact]:
        return list(
            ProjectContact.objects.filter(contact_id=contact_id)
            .select_related("project")
            .order_by("role", "project__name")
        )

    @staticmethod
    def history_for_contact(contact_id: int) -> list[ProjectContactHistory]:
        return list(
            ProjectContactHistory.objects.filter(contact_id=contact_id)
            .select_related("project")
            .order_by("-created_at")
        )


class ProjectLinkService:
    @staticmethod
    def list_links(project_id: int, search=None, page=1, page_size=20):
        qs = ProjectLink.objects.filter(project_id=project_id)
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(url__icontains=search))
        qs.order_by("title")

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
    def get_link(project_id: int, link_id: int):
        return ProjectLink.objects.get(pk=link_id, project_id=project_id)

    @staticmethod
    @transaction.atomic
    def create_link(project_id, title, url):
        project = Project.objects.get(pk=project_id)
        if not project:
            raise ValidationError(f"Project '{project_id}' does not exist.")

        try:
            return ProjectLink.objects.create(
                project_id=project_id,
                title=title.strip(),
                url=url.strip(),
            )
        except IntegrityError as e:
            logger.error("IntegrityError creating project link '%s': %s", project_id, e)
            raise ValidationError(
                f"Project link for project '{project_id}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "DatabaseError creating project link '%s': %s", project_id, e
            )
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating project link '%s': %s",
                project_id,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_link(link, *, title=None, url=None):
        if title is not None:
            link.title = title.strip()
        if url is not None:
            link.url = url.strip()

        try:
            link.save()
            return link
        except IntegrityError as e:
            logger.error("IntegrityError updating project link %s: %s", link, e)
            raise ValidationError(
                "Project could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating project link %s: %s", link, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating project link '%s': %s",
                link,
                e,
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_link(link):
        try:
            link.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting project link %s: %s", link, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting project link '%s': %s",
                link,
                e,
            )
            raise


class ProjectViewService:

    VALID_ORDER_FIELDS = {
        "name",
        "-name",
        "created_at",
        "-created_at",
        "updated_at",
        "-updated_at",
    }

    @staticmethod
    def list_all():
        return ProjectView.objects.all().order_by("name")

    @staticmethod
    def get(pk):
        try:
            return ProjectView.objects.get(pk=pk)
        except ProjectView.DoesNotExist:
            raise ProjectView.DoesNotExist

    @staticmethod
    def create(
        name, filters=None, columns=None, ordering="-created_at", is_default=False
    ):
        name = (name or "").strip()
        if not name:
            raise ValidationError({"name": "Name is required."})
        if ProjectView.objects.filter(name__iexact=name).exists():
            raise ValidationError({"name": f'A view named "{name}" already exists.'})

        view = ProjectView(
            name=name,
            filters=filters or {},
            columns=columns or [],
            ordering=ordering or "-created_at",
            is_default=bool(is_default),
        )
        if view.is_default:
            ProjectView.objects.filter(is_default=True).update(is_default=False)
        view.save()
        return view

    @staticmethod
    def update(pk, **kwargs):
        try:
            view = ProjectView.objects.get(pk=pk)
        except ProjectView.DoesNotExist:
            raise

        if "name" in kwargs:
            name = (kwargs["name"] or "").strip()
            if not name:
                raise ValidationError({"name": "Name is required."})
            if ProjectView.objects.filter(name__iexact=name).exclude(pk=pk).exists():
                raise ValidationError(
                    {"name": f'A view named "{name}" already exists.'}
                )
            view.name = name

        if "filters" in kwargs and kwargs["filters"] is not None:
            view.filters = kwargs["filters"]

        if "columns" in kwargs and kwargs["columns"] is not None:
            view.columns = kwargs["columns"]

        if "ordering" in kwargs:
            view.ordering = kwargs["ordering"] or "-created_at"

        if "is_default" in kwargs:
            view.is_default = bool(kwargs["is_default"])
            if view.is_default:
                ProjectView.objects.filter(is_default=True).exclude(pk=pk).update(
                    is_default=False
                )

        view.save()
        return view

    @staticmethod
    def delete(pk):
        try:
            view = ProjectView.objects.get(pk=pk)
        except ProjectView.DoesNotExist:
            raise
        view.delete()

    @staticmethod
    def get_default():
        return ProjectView.objects.filter(is_default=True).first()


class ProjectAttachmentService:
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    @staticmethod
    def _get_storage_backend():
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_value("PROJECT_ATTACHMENT_STORAGE") or "database"
        except Exception:
            return "database"

    @staticmethod
    def list_attachments(project_id: int):
        return list(
            ProjectAttachment.objects.filter(project_id=project_id)
            .defer("file_data")
            .order_by("-created_at")
        )

    @staticmethod
    def get_attachment(project_id: int, attachment_id: int):
        return ProjectAttachment.objects.get(pk=attachment_id, project_id=project_id)

    @staticmethod
    @transaction.atomic
    def save_attachment(project_id: int, file_obj, uploaded_by: str = ""):
        from apps.configurations.services import ConfigurationService

        if file_obj.size > ProjectAttachmentService.MAX_FILE_SIZE:
            raise ValidationError("File exceeds the 50 MB size limit.")

        backend = ProjectAttachmentService._get_storage_backend()
        att = ProjectAttachment(
            project_id=project_id,
            file_name=file_obj.name,
            content_type=getattr(file_obj, "content_type", "") or "",
            file_size=file_obj.size,
            uploaded_by=uploaded_by,
        )

        if backend == "local":
            import os
            local_path = ConfigurationService.get_value("PROJECT_ATTACHMENT_LOCAL_PATH") or ""
            if not local_path:
                raise ValidationError("PROJECT_ATTACHMENT_LOCAL_PATH is not configured.")
            os.makedirs(local_path, exist_ok=True)
            dest = os.path.join(local_path, f"{project_id}_{file_obj.name}")
            with open(dest, "wb") as fh:
                for chunk in file_obj.chunks():
                    fh.write(chunk)
            att.file_path = dest
        elif backend == "s3":
            try:
                import boto3
                bucket_arn = ConfigurationService.get_value("PROJECT_ATTACHMENT_S3_BUCKET_ARN") or ""
                bucket_name = bucket_arn.split(":::")[-1] if ":::" in bucket_arn else bucket_arn
                s3_key = f"project-attachments/{project_id}/{file_obj.name}"
                s3 = boto3.client("s3")
                s3.upload_fileobj(file_obj, bucket_name, s3_key)
                att.s3_key = s3_key
            except ImportError:
                raise ValidationError("boto3 is required for S3 storage.")
        else:
            att.file_data = file_obj.read()

        att.save()
        return att

    @staticmethod
    def get_file_bytes(attachment: ProjectAttachment) -> tuple[bytes, str]:
        backend = ProjectAttachmentService._get_storage_backend()
        if backend == "local":
            with open(attachment.file_path, "rb") as fh:
                return fh.read(), attachment.content_type
        elif backend == "s3":
            try:
                import boto3
                from apps.configurations.services import ConfigurationService
                bucket_arn = ConfigurationService.get_value("PROJECT_ATTACHMENT_S3_BUCKET_ARN") or ""
                bucket_name = bucket_arn.split(":::")[-1] if ":::" in bucket_arn else bucket_arn
                s3 = boto3.client("s3")
                resp = s3.get_object(Bucket=bucket_name, Key=attachment.s3_key)
                return resp["Body"].read(), attachment.content_type
            except ImportError:
                raise RuntimeError("boto3 is required for S3 storage.")
        else:
            data = attachment.file_data
            return bytes(data) if data else b"", attachment.content_type

    @staticmethod
    @transaction.atomic
    def delete_attachment(attachment: ProjectAttachment):
        backend = ProjectAttachmentService._get_storage_backend()
        if backend == "local" and attachment.file_path:
            import os
            try:
                os.remove(attachment.file_path)
            except OSError:
                pass
        elif backend == "s3" and attachment.s3_key:
            try:
                import boto3
                from apps.configurations.services import ConfigurationService
                bucket_arn = ConfigurationService.get_value("PROJECT_ATTACHMENT_S3_BUCKET_ARN") or ""
                bucket_name = bucket_arn.split(":::")[-1] if ":::" in bucket_arn else bucket_arn
                boto3.client("s3").delete_object(Bucket=bucket_name, Key=attachment.s3_key)
            except ImportError:
                pass
        attachment.delete()
