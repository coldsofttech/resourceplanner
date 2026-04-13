import csv
from decimal import Decimal
import io
import logging

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction, IntegrityError, DatabaseError
from django.db.models import Q

from apps.core.utils import parse_bool

from .models import Programme

logger = logging.getLogger(__name__)

PROTECTED_PROGRAMME_NAME = "Others"


class ProgrammeService:
    @staticmethod
    def _guard_protected(programme):
        """Raise ValidationError if the programme is the protected default."""
        if programme.name == PROTECTED_PROGRAMME_NAME:
            raise ValidationError(
                f"'{PROTECTED_PROGRAMME_NAME}' is a default programme and cannot be modified or deleted."
            )

    @staticmethod
    def list_programmes(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {"name", "is_active"}
        qs = Programme.objects.all()

        if filters:
            if filters.get("search"):
                s_term = filters["search"]
                qs = qs.filter(
                    Q(name__icontains=s_term) | Q(description__icontains=s_term)
                )
            if filters.get("is_active") is not None:
                is_active_raw = filters["is_active"]
                is_active = parse_bool(is_active_raw)
                qs = qs.filter(is_active=is_active)

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

        qs = Programme.objects.all()
        result = {}

        if wants("total_programmes"):
            result["total_programmes"] = qs.count()
        if wants("active_programmes"):
            result["active_programmes"] = qs.filter(is_active=True).count()
        if wants("inactive_programmes"):
            result["inactive_programmes"] = qs.filter(is_active=False).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        result = {}

        if wants("is_active"):
            result["is_active"] = [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]

        return result

    @staticmethod
    def get_programme(programme_id: int):
        if not programme_id:
            raise ValidationError("Invalid: programme_id must be a positive integer.")

        return Programme.objects.get(pk=programme_id)

    @staticmethod
    @transaction.atomic
    def create_programme(data: dict):
        if not isinstance(data, dict) or "name" not in data:
            raise ValidationError("Invalid: data must be a dict containing 'name'.")

        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")

        if Programme.objects.filter(name=name).exists():
            raise ValidationError(f"Programme '{name}' already exists.")

        try:
            programme = Programme(
                name=name,
                description=(data.get("description") or "").strip(),
                is_active=data.get("is_active", True),
            )
            programme.full_clean()
            programme.save()
            return programme
        except IntegrityError as e:
            logger.error("IntegrityError creating programme '%s': %s", name, e)
            raise ValidationError(
                f"Programme '{name}' could not be created due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError creating programme '%s': %s", name, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when creating programme '%s': %s", name, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def update_programme(programme_id: int, data: dict):
        if not programme_id:
            raise ValidationError("Invalid: programme_id must be a positive integer.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        programme = Programme.objects.get(pk=programme_id)
        if not programme:
            raise ValidationError(f"Programme '{programme_id}' does not exist.")

        ProgrammeService._guard_protected(programme)

        if "name" in data:
            new_name = data["name"].strip()
            if not new_name:
                raise ValidationError("Invalid: name cannot be blank.")
            if (
                Programme.objects.filter(name=new_name)
                .exclude(pk=programme_id)
                .exists()
            ):
                raise ValidationError(f"Programme '{new_name}' already exists.")
            programme.name = new_name
        if "description" in data:
            programme.description = (data["description"] or "").strip()
        if "is_active" in data:
            programme.is_active = data["is_active"]

        try:
            programme.full_clean()
            programme.save()
            return programme
        except IntegrityError as e:
            logger.error("IntegrityError updating programme %s: %s", programme_id, e)
            raise ValidationError(
                f"Programme could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception("DatabaseError updating programme %s: %s", programme_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating programme '%s': %s", programme_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def delete_programme(programme_id: int):
        if not programme_id:
            raise ValidationError("Invalid: programme_id must be a positive integer.")

        programme = Programme.objects.get(pk=programme_id)
        if not programme:
            raise ValidationError(f"Programme '{programme_id}' does not exist.")

        ProgrammeService._guard_protected(programme)

        try:
            programme.delete()
        except DatabaseError as e:
            logger.exception("DatabaseError deleting programme %s: %s", programme_id, e)
            raise RuntimeError(
                "A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when deleting programme '%s': %s", programme_id, e
            )
            raise

    @staticmethod
    def _validate_row(data: dict):
        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("'name' is required and cannot be blank.")
        if len(name) > 100:
            raise ValidationError("'name' must be 100 characters or fewer.")
        if Programme.objects.filter(name=name).exists():
            raise ValidationError(f"Programme '{name}' already exists.")

    @staticmethod
    def bulk_import(request, dry_run=False):
        file = request.FILES.get("file")
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith(".csv"):
            raise ValidationError("Only CSV files are supported.")

        rows: list[dict] = []
        try:
            decoded = file.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError:
            logger.warning("Unicode error reading import file.")
            raise ValidationError("File must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"Maximum {MAX_ROWS} rows allowed per import.")

        results = {
            "succeeded": [],
            "failed": [],
            "total": len(rows),
            "dry_run": dry_run,
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):  # start=2 accounts for header row
            name = (row.get("name") or "").strip()
            label = name or f"(row {index})"

            try:
                data = {
                    "name": name,
                    "description": row.get("description", "").strip(),
                    "is_active": (row.get("is_active") or "true").strip().lower()
                    == "true",
                }

                if dry_run:
                    ProgrammeService._validate_row(data)
                    results["succeeded"].append({"row": index, "name": label})
                else:
                    ProgrammeService.create_programme(data)
                    results["succeeded"].append({"row": index, "name": label})
            except (
                ValidationError,
                ValueError,
                IntegrityError,
                DatabaseError,
                Exception,
            ) as e:
                results["failed"].append(
                    {
                        "row": index,
                        "name": label,
                        "error": e.messages if hasattr(e, "messages") else str(e),
                    }
                )

        if dry_run:
            results["summary"] = (
                f"Validation complete: {len(results['succeeded'])} rows valid, "
                f"{len(results['failed'])} rows have errors."
            )
        else:
            results["summary"] = (
                f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
            )

        return results

    @staticmethod
    def get_programme_summary(
        programme_id: int, fy_id: int = None, page: int = 1, page_size: int = 20
    ):
        if not programme_id:
            raise ValidationError("Invalid: programme_id cannot be blank.")

        from apps.configurations.services import ConfigurationService
        from apps.projects.models import Project, ProjectBudget
        from apps.projects.services import ProjectBudgetService
        from apps.financial_years.models import FinancialYear

        programme = Programme.objects.get(pk=programme_id)
        threshold_pct = Decimal(
            str(ConfigurationService.get_float("BUDGET_THRESHOLD_PCT", fallback=10.0))
        )

        all_projects = (
            Project.objects.filter(programme=programme)
            .exclude(status=Project.STATUS_CANCELLED)
            .select_related("assigned_team")
            .order_by("name")
        )

        if fy_id:
            all_fys = FinancialYear.objects.filter(id=fy_id).order_by("-start_date")
        else:
            all_fys = FinancialYear.objects.order_by("-start_date")

        total_actual_budget = Decimal("0")
        total_estimated_cost = Decimal("0")
        total_remaining_budget = Decimal("0")

        final_qs = []

        for proj in all_projects:
            for fy in all_fys:
                budget = (
                    ProjectBudget.objects.filter(
                        project_id=proj.pk, financial_year_id=fy.pk
                    )
                    .select_related("estimate_version")
                    .first()
                )

                actual_budget = budget.actual_budget if budget else None
                est_cost = (
                    budget.estimate_version.total_cost
                    if budget and budget.estimate_version
                    else None
                )
                remaining_budget = budget.remaining_budget if budget else None
                enriched_budget = ProjectBudgetService._enrich(budget)
                row_risk = (
                    getattr(enriched_budget, "_budget_risk")
                    if hasattr(enriched_budget, "_budget_risk")
                    else None
                )
                row_risk_display = (
                    getattr(enriched_budget, "_budget_risk_display")
                    if hasattr(enriched_budget, "_budget_risk_display")
                    else None
                )
                row_risk_short = (
                    getattr(enriched_budget, "_budget_risk_short")
                    if hasattr(enriched_budget, "_budget_risk_short")
                    else None
                )
                row_risk_pct = (
                    getattr(enriched_budget, "_budget_risk_pct")
                    if hasattr(enriched_budget, "_budget_risk_pct")
                    else None
                )

                if actual_budget is not None:
                    total_actual_budget += actual_budget
                if est_cost is not None:
                    total_estimated_cost += Decimal(str(est_cost))
                if remaining_budget is not None:
                    total_remaining_budget += remaining_budget

                final_qs.append(
                    {
                        "id": proj.pk,
                        "name": proj.name,
                        "status": proj.get_status_display(),
                        "financial_year": fy.long_fy,
                        "assigned_team": (
                            proj.assigned_team.name if proj.assigned_team else None
                        ),
                        "actual_budget": actual_budget,
                        "estimate_total_cost": est_cost,
                        "remaining_budget": remaining_budget,
                        "risk": row_risk,
                        "risk_pct": row_risk_pct,
                        "risk_display": row_risk_display,
                        "risk_short": row_risk_short,
                    }
                )

        programme_risk_pct = None
        programme_risk_display = None
        programme_risk_short = None
        programme_risk = None
        if total_actual_budget != Decimal("0"):
            variance_pct = (
                (total_estimated_cost - total_actual_budget) / total_actual_budget * 100
            )
            abs_variance = abs(variance_pct)
            sign = "+" if variance_pct >= 0 else ""
            programme_risk_pct = f"{sign}{variance_pct:.2f}"
            abs_variance = abs(variance_pct)

            if abs_variance <= Decimal("1.00"):
                programme_risk_display = "On Budget"
                programme_risk_short = "OB"
                programme_risk = "GREEN"
            elif abs_variance <= threshold_pct:
                programme_risk = "AMBER"
                if variance_pct > 0:
                    programme_risk_display = "At Risk (Over)"
                    programme_risk_short = "AR+"
                else:
                    programme_risk_display = "At Risk (Under)"
                    programme_risk_short = "AR-"
            else:
                programme_risk = "RED"
                if variance_pct > 0:
                    programme_risk_display = "Over Budget"
                    programme_risk_short = "OVR"
                else:
                    programme_risk_display = "Under Budget"
                    programme_risk_short = "UND"

        paginator = Paginator(final_qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": list(page_obj.object_list),
            "summary": {
                "actual_budget": total_actual_budget,
                "estimated_cost": total_estimated_cost,
                "remaining_budget": total_remaining_budget,
                "risk_pct": programme_risk_pct,
                "risk_display": programme_risk_display,
                "risk_short": programme_risk_short,
                "risk": programme_risk,
            },
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }
