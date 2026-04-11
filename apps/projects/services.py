import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Q

from apps.core.utils import parse_bool

from .models import Project, ProjectCollaborator

logger = logging.getLogger(__name__)


class ProjectService:

    @staticmethod
    def list_projects(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {"name", "status", "priority"}

        qs = Project.objects.select_related(
            "project_type", "programme", "sub_status", "assigned_team"
        ).all()

        if filters:
            search = filters.get("search")
            if search:
                qs = qs.filter(
                    Q(name__icontains=search)
                    | Q(programme__name__icontains=search)
                    | Q(code__icontains=search)
                )

            def _vals(key):
                raw = filters.get(key) or ""
                return [v.strip() for v in raw.split(",") if v.strip()]

            is_active_vals = _vals("is_active")
            if is_active_vals:
                bool_map = {"true": True, "false": False}
                bools = [bool_map[v] for v in is_active_vals if v in bool_map]
                if bools:
                    qs = qs.filter(is_active__in=bools)

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

            team_vals = _vals("team")
            if team_vals:
                qs = qs.filter(
                    Q(assigned_team_id__in=team_vals)
                    | Q(project_collaborators__team_id__in=team_vals)
                ).distinct()

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
    def create_project(data: dict):
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
        code = (data.get("code") or "").strip()
        status = data.get("status") or Project.STATUS_NEW

        ProjectService._enforce_in_progress_rules(status, code, assigned_team_id)

        try:
            project = Project(
                name=name,
                project_type_id=project_type_id,
                programme_id=programme_id,
                code=code,
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
