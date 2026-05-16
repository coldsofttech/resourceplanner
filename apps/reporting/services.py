import csv
import io
import logging
from datetime import timedelta

from django.db.models import Case, Count, DecimalField, F, Sum, When

logger = logging.getLogger(__name__)

LEAVE_CATEGORY = "HOLIDAYS/LEAVES"

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REPORT_REGISTRY = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sprint_working_days(sprint):
    """Count Mon–Fri days within a sprint's start/end date range."""
    count = 0
    cur = sprint.start_date
    while cur <= sprint.end_date:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return max(count, 1)


def _r2(v):
    return round(float(v or 0), 2)


# ---------------------------------------------------------------------------
# Report list service
# ---------------------------------------------------------------------------

class ReportService:
    @staticmethod
    def list_reports(report_type=None):
        from .models import Report

        qs = Report.objects.filter(is_active=True)
        if report_type:
            types = [t.strip().upper() for t in report_type.split(",")]
            qs = qs.filter(report_type__in=types)
        return list(qs)

    @staticmethod
    def get_report_by_slug(slug):
        from .models import Report

        return Report.objects.get(slug=slug, is_active=True)

    @staticmethod
    def create_custom_report(data, user=None):
        from .models import Report

        return Report.objects.create(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description", ""),
            report_type=Report.CUSTOM,
            is_active=True,
            sort_order=data.get("sort_order", 0),
            created_by=user,
            updated_by=user,
        )


# ---------------------------------------------------------------------------
# Demand & Capacity — config service
# ---------------------------------------------------------------------------

class DemandCapacityConfigService:
    @staticmethod
    def get_or_create(plan_id, version_id, user=None):
        from apps.resource_plans.models import ResourcePlan, ResourcePlanVersion

        from .models import DemandCapacityConfig

        plan = ResourcePlan.objects.get(pk=plan_id)
        version = ResourcePlanVersion.objects.get(pk=version_id)
        config, created = DemandCapacityConfig.objects.get_or_create(
            plan=plan,
            version=version,
            defaults={"created_by": user, "updated_by": user},
        )
        if not created and user:
            config.updated_by = user
            config.save(update_fields=["updated_by", "updated_at"])
        return config

    @staticmethod
    def get_configure_data(plan_id, version_id):
        from apps.programmes.models import Programme
        from apps.resource_plans.models import (
            ResourcePlan,
            ResourcePlanVersion,
            ResourcePlanVersionProject,
        )

        from .models import DemandCapacityConfig

        try:
            plan = ResourcePlan.objects.get(pk=plan_id)
            version = ResourcePlanVersion.objects.get(pk=version_id)
        except (ResourcePlan.DoesNotExist, ResourcePlanVersion.DoesNotExist):
            return None

        programme_ids = set(
            ResourcePlanVersionProject.objects.filter(
                version=version,
                project__programme__isnull=False,
            ).values_list("project__programme_id", flat=True)
        )
        programmes = list(Programme.objects.filter(id__in=programme_ids).order_by("name"))

        try:
            config = DemandCapacityConfig.objects.get(plan=plan, version=version)
            mappings = list(config.mappings.select_related("programme").all())
            mapping_dict = {m.programme_id: m for m in mappings}
        except DemandCapacityConfig.DoesNotExist:
            config = None
            mapping_dict = {}

        return {
            "plan": plan,
            "version": version,
            "config": config,
            "programmes": programmes,
            "mapping_dict": mapping_dict,
        }

    @staticmethod
    def list_mappings(plan_id, version_id):
        from .models import ProgrammeCategoryMapping

        return (
            ProgrammeCategoryMapping.objects.filter(
                config__plan_id=plan_id,
                config__version_id=version_id,
            )
            .select_related("programme", "config")
            .order_by("programme__name")
        )

    @staticmethod
    def upsert_mapping(plan_id, version_id, programme_id, category_label, user=None):
        from apps.programmes.models import Programme

        from .models import ProgrammeCategoryMapping

        config = DemandCapacityConfigService.get_or_create(plan_id, version_id, user)
        programme = Programme.objects.get(pk=programme_id)
        mapping, created = ProgrammeCategoryMapping.objects.update_or_create(
            config=config,
            programme=programme,
            defaults={"category_label": category_label, "created_by": user},
        )
        return mapping, created

    @staticmethod
    def delete_mapping(mapping_id):
        from .models import ProgrammeCategoryMapping

        ProgrammeCategoryMapping.objects.filter(pk=mapping_id).delete()

    @staticmethod
    def bulk_upsert_mappings(plan_id, version_id, mappings, user=None):
        """
        Each item: {programme_id, category_label}.
        Empty label → delete existing mapping for that programme.
        """
        from .models import ProgrammeCategoryMapping

        config = DemandCapacityConfigService.get_or_create(plan_id, version_id, user)
        results = []
        for item in mappings:
            prog_id = item["programme_id"]
            label = item.get("category_label", "").strip()
            if not label:
                ProgrammeCategoryMapping.objects.filter(
                    config=config, programme_id=prog_id
                ).delete()
                continue
            mapping, created = ProgrammeCategoryMapping.objects.update_or_create(
                config=config,
                programme_id=prog_id,
                defaults={"category_label": label, "created_by": user},
            )
            results.append({"mapping": mapping, "created": created})
        return results


# ---------------------------------------------------------------------------
# Demand & Capacity — report data service
# ---------------------------------------------------------------------------

class DemandCapacityService:

    @staticmethod
    def get_data(plan_id, version_id, team_id=None, employee_type_id=None):
        from apps.delivery_teams.models import DeliveryTeam
        from apps.programmes.models import Programme
        from apps.resource_plans.models import (
            ResourcePlan,
            ResourcePlanAllocation,
            ResourcePlanAllocationSet,
            ResourcePlanMemberCapacity,
            ResourcePlanVersion,
        )
        from apps.sprints.models import Sprint

        from .models import DemandCapacityConfig

        try:
            plan = ResourcePlan.objects.select_related("financial_year").get(pk=plan_id)
            version = ResourcePlanVersion.objects.get(pk=version_id)
        except (ResourcePlan.DoesNotExist, ResourcePlanVersion.DoesNotExist):
            return None

        # ── Sprints & month structure ──────────────────────────────────────
        sprints = list(
            Sprint.objects.filter(financial_year=plan.financial_year)
            .order_by("sprint_number")
        )
        sprint_ids = [s.id for s in sprints]

        months_order = []          # ordered unique month keys
        sprint_to_month = {}       # sprint.id → month_key
        month_working_days = {}    # month_key → sum of business days across sprints
        month_labels = {}          # month_key → display label
        seen_months: set = set()

        for s in sprints:
            wd = _sprint_working_days(s)
            mkey = f"{s.end_date.year}-{s.month}"
            if mkey not in seen_months:
                seen_months.add(mkey)
                months_order.append(mkey)
                month_labels[mkey] = f"{s.month} '{str(s.end_date.year)[2:]}"
                month_working_days[mkey] = 0
            sprint_to_month[s.id] = mkey
            month_working_days[mkey] += wd

        # ── Category mappings (fresh from DB — no cache) ───────────────────
        try:
            config = DemandCapacityConfig.objects.get(plan=plan, version=version)
            mapping_dict = {
                m.programme_id: m.category_label
                for m in config.mappings.all()
            }
        except DemandCapacityConfig.DoesNotExist:
            mapping_dict = {}

        def _category(prog_id, prog_names):
            return mapping_dict.get(prog_id, prog_names.get(prog_id, str(prog_id)))

        # ── Active allocation set ──────────────────────────────────────────
        alloc_set = (
            ResourcePlanAllocationSet.objects.filter(
                version=version,
                status=ResourcePlanAllocationSet.STATUS_ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )

        # ── Demand: raw days per (team, sprint, programme) ─────────────────
        demand_rows = []
        if alloc_set:
            qs = ResourcePlanAllocation.objects.filter(
                allocation_set=alloc_set,
                programme__isnull=False,
                sprint_id__in=sprint_ids,
                placeholder_engineer__isnull=True,  # Exclude AUTO #X placeholder slots
            )
            if team_id:
                qs = qs.filter(team_id=team_id)
            if employee_type_id:
                qs = qs.filter(team_member__employment_type_id=employee_type_id)

            demand_rows = list(
                qs.values("team_id", "sprint_id", "programme_id").annotate(
                    total=Sum(
                        Case(
                            When(override_days__isnull=False, then=F("override_days")),
                            default=F("engine_days"),
                            output_field=DecimalField(),
                        )
                    )
                )
            )

        prog_ids_needed = {r["programme_id"] for r in demand_rows}
        prog_names = {
            p.id: p.name
            for p in Programme.objects.filter(id__in=prog_ids_needed)
        }

        # ── Capacity & leaves: gross working_days per (team, sprint) ──────
        cap_qs = ResourcePlanMemberCapacity.objects.filter(
            version=version, sprint_id__in=sprint_ids
        )
        if team_id:
            cap_qs = cap_qs.filter(team_member__team_id=team_id)
        if employee_type_id:
            cap_qs = cap_qs.filter(team_member__employment_type_id=employee_type_id)

        cap_rows = list(
            cap_qs.values("sprint_id", "team_member__team_id").annotate(
                working=Sum("working_days"),
                leaves=Sum(F("leave_days") + F("holiday_days") + F("placeholder_days")),
            )
        )

        # ── Aggregate demand into: {team_id: {category: {month_key: days}}} ─
        def _build_cat_days(rows, team_filter=None):
            """Accumulate raw demand days by category × month."""
            cat_days: dict = {}
            for r in rows:
                if team_filter is not None and r["team_id"] != team_filter:
                    continue
                mkey = sprint_to_month.get(r["sprint_id"])
                if not mkey:
                    continue
                cat = _category(r["programme_id"], prog_names)
                cat_days.setdefault(cat, {})
                cat_days[cat][mkey] = cat_days[cat].get(mkey, 0.0) + float(r["total"] or 0)
            return cat_days

        def _days_to_fte(cat_days):
            """Convert {cat: {month: days}} → {cat: {month: fte}}."""
            out = {}
            for cat, md in cat_days.items():
                out[cat] = {}
                for mkey, days in md.items():
                    wd = month_working_days.get(mkey, 1)
                    out[cat][mkey] = _r2(days / wd) if wd else 0.0
            return out

        def _sprint_to_month_raw(by_sprint):
            """Sum raw values per month, then convert to FTE."""
            by_month: dict = {}
            for sid, val in by_sprint.items():
                mkey = sprint_to_month.get(sid)
                if mkey:
                    by_month[mkey] = by_month.get(mkey, 0.0) + val
            return {
                mkey: _r2(days / month_working_days.get(mkey, 1))
                for mkey, days in by_month.items()
            }

        # Overall demand FTE by category
        overall_cat_days = _build_cat_days(demand_rows)
        overall_demand_fte = _days_to_fte(overall_cat_days)

        # Seed all configured category labels so they appear even with 0 demand
        for cat_label in mapping_dict.values():
            if cat_label and cat_label not in overall_demand_fte:
                overall_demand_fte[cat_label] = {}

        # Overall capacity + leave FTE
        cap_by_sprint: dict = {}
        leave_by_sprint: dict = {}
        team_cap_by_sprint: dict = {}   # {(tid, sid): working_days}
        team_leave_by_sprint: dict = {} # {(tid, sid): leave_days}

        for r in cap_rows:
            sid = r["sprint_id"]
            tid = r["team_member__team_id"]
            w = float(r["working"] or 0)
            lv = float(r["leaves"] or 0)
            cap_by_sprint[sid] = cap_by_sprint.get(sid, 0.0) + w
            leave_by_sprint[sid] = leave_by_sprint.get(sid, 0.0) + lv
            team_cap_by_sprint[(tid, sid)] = team_cap_by_sprint.get((tid, sid), 0.0) + w
            team_leave_by_sprint[(tid, sid)] = team_leave_by_sprint.get((tid, sid), 0.0) + lv

        overall_cap_fte = _sprint_to_month_raw(cap_by_sprint)
        overall_leave_fte = _sprint_to_month_raw(leave_by_sprint)

        # Add HOLIDAYS/LEAVES as a demand-side category so it stacks in the chart
        if overall_leave_fte:
            overall_demand_fte[LEAVE_CATEGORY] = overall_leave_fte

        # Build ordered categories: sorted regular + HOLIDAYS/LEAVES last
        regular_cats = sorted(
            cat for cat in overall_demand_fte if cat != LEAVE_CATEGORY
        )
        all_categories = regular_cats + (
            [LEAVE_CATEGORY] if LEAVE_CATEGORY in overall_demand_fte else []
        )

        # ── Per-team breakdown ─────────────────────────────────────────────
        team_ids = set()
        for r in demand_rows:
            if r["team_id"]:
                team_ids.add(r["team_id"])
        for (tid, _) in team_cap_by_sprint:
            if tid:
                team_ids.add(tid)

        teams_data = []
        if team_ids:
            teams_qs = DeliveryTeam.objects.filter(id__in=team_ids).order_by("name")
            for team in teams_qs:
                tid = team.id

                t_cat_days = _build_cat_days(demand_rows, team_filter=tid)
                t_demand_fte = _days_to_fte(t_cat_days)

                t_cap_raw = {
                    sid: v for (t, sid), v in team_cap_by_sprint.items() if t == tid
                }
                t_leave_raw = {
                    sid: v for (t, sid), v in team_leave_by_sprint.items() if t == tid
                }
                t_cap_fte = _sprint_to_month_raw(t_cap_raw)
                t_leave_fte = _sprint_to_month_raw(t_leave_raw)

                if t_leave_fte:
                    t_demand_fte[LEAVE_CATEGORY] = t_leave_fte

                t_demand_by_month = _totals_by_month(t_demand_fte, months_order)
                t_risk, t_util = _risk_util(t_demand_by_month, t_cap_fte, months_order)

                teams_data.append({
                    "id": tid,
                    "name": team.name,
                    "demand": t_demand_fte,
                    "capacity": t_cap_fte,
                    "totals": {
                        "demand_by_month": t_demand_by_month,
                        "demand_total": _r2(sum(t_demand_by_month.values())),
                        "capacity_total": _r2(sum(t_cap_fte.values())),
                        "risk_by_month": t_risk,
                        "utilisation_by_month": t_util,
                    },
                })

        # ── Overall totals ─────────────────────────────────────────────────
        demand_by_month = _totals_by_month(overall_demand_fte, months_order)
        risk_by_month, util_by_month = _risk_util(
            demand_by_month, overall_cap_fte, months_order
        )

        months_list = [
            {
                "key": k,
                "label": month_labels[k],
                "working_days": month_working_days[k],
            }
            for k in months_order
        ]

        return {
            "plan": {"id": plan.id, "name": plan.name},
            "version": {
                "id": version.id,
                "version": version.version,
                "status": version.status,
            },
            "months": months_list,
            "categories": all_categories,
            "demand": overall_demand_fte,
            "capacity": overall_cap_fte,
            "totals": {
                "demand_by_month": demand_by_month,
                "demand_total": _r2(sum(demand_by_month.values())),
                "capacity_total": _r2(sum(overall_cap_fte.values())),
                "risk_by_month": risk_by_month,
                "utilisation_by_month": util_by_month,
            },
            "teams": teams_data,
            "has_allocation_set": alloc_set is not None,
        }

    # ── Export helpers ─────────────────────────────────────────────────────

    @staticmethod
    def export_csv(data: dict) -> bytes:
        months = data["months"]
        categories = data["categories"]
        demand = data["demand"]
        capacity = data["capacity"]
        totals = data["totals"]

        buf = io.StringIO()
        w = csv.writer(buf)

        # Header
        w.writerow(["Category"] + [m["label"] for m in months] + ["Total"])

        # Demand rows
        for cat in categories:
            cat_data = demand.get(cat, {})
            row_vals = [cat_data.get(m["key"], 0.0) for m in months]
            w.writerow([cat] + [f"{v:.2f}" for v in row_vals] + [f"{sum(row_vals):.2f}"])

        # Total Demand
        td = [totals["demand_by_month"].get(m["key"], 0.0) for m in months]
        w.writerow(["Total Demand"] + [f"{v:.2f}" for v in td] + [f"{sum(td):.2f}"])

        # Total Capacity
        tc = [capacity.get(m["key"], 0.0) for m in months]
        w.writerow(["Total Capacity"] + [f"{v:.2f}" for v in tc] + [f"{sum(tc):.2f}"])

        # FTE Risk
        tr = [totals["risk_by_month"].get(m["key"], 0.0) for m in months]
        w.writerow(["FTE Risk"] + [f"{v:.2f}" for v in tr] + [f"{sum(tr):.2f}"])

        # Utilisation %
        tu = [totals["utilisation_by_month"].get(m["key"], 0.0) for m in months]
        w.writerow(["Utilisation %"] + [f"{v:.2f}%" for v in tu] + [""])

        return buf.getvalue().encode("utf-8-sig")

    @staticmethod
    def export_xlsx(data: dict) -> bytes:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        months = data["months"]
        categories = data["categories"]
        demand = data["demand"]
        capacity = data["capacity"]
        totals = data["totals"]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Demand & Capacity"

        H_FILL  = PatternFill("solid", fgColor="1F4E79")
        TD_FILL = PatternFill("solid", fgColor="DBEAFE")
        TC_FILL = PatternFill("solid", fgColor="D1FAE5")
        RK_FILL = PatternFill("solid", fgColor="FEF3C7")
        LV_FILL = PatternFill("solid", fgColor="F3F4F6")
        CENTER  = Alignment(horizontal="center")

        def hdr_cell(row, col, val):
            c = ws.cell(row, col, val)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = H_FILL
            c.alignment = CENTER
            return c

        def styled_row(row, col_start, values, fill, bold=False, fmt="{:.2f}"):
            for i, v in enumerate(values):
                c = ws.cell(row, col_start + i, float(v) if isinstance(v, (int, float)) else v)
                c.fill = fill
                c.alignment = CENTER
                if bold:
                    c.font = Font(bold=True)

        n = len(months)
        total_col = n + 2

        # Header row
        hdr_cell(1, 1, "Category")
        for ci, m in enumerate(months, 2):
            hdr_cell(1, ci, m["label"])
        hdr_cell(1, total_col, "Total")

        # Category demand rows
        PALETTE = [
            "BFD7FF","C6F6D5","FDE68A","FCA5A5","DDD6FE",
            "A5F3FC","FED7AA","D9F99D","FBCFE8","C7D2FE",
        ]
        next_row = 2
        for idx, cat in enumerate(categories):
            cat_data = demand.get(cat, {})
            fill_hex = "F9FAFB" if cat == LEAVE_CATEGORY else PALETTE[idx % len(PALETTE)]
            fill = PatternFill("solid", fgColor=fill_hex)
            ws.cell(next_row, 1, cat).font = Font(italic=(cat == LEAVE_CATEGORY))
            ws.cell(next_row, 1).fill = fill
            row_vals = [cat_data.get(m["key"], 0.0) for m in months]
            for ci, v in enumerate(row_vals, 2):
                c = ws.cell(next_row, ci, round(v, 2))
                c.alignment = CENTER
                c.fill = fill
            ws.cell(next_row, total_col, round(sum(row_vals), 2)).alignment = CENTER
            ws.cell(next_row, total_col).fill = fill
            next_row += 1

        # Total Demand
        td = [totals["demand_by_month"].get(m["key"], 0.0) for m in months]
        ws.cell(next_row, 1, "Total Demand").font = Font(bold=True)
        ws.cell(next_row, 1).fill = TD_FILL
        styled_row(next_row, 2, td + [sum(td)], TD_FILL, bold=True)
        next_row += 1

        # Total Capacity
        tc = [capacity.get(m["key"], 0.0) for m in months]
        ws.cell(next_row, 1, "Total Capacity").font = Font(bold=True)
        ws.cell(next_row, 1).fill = TC_FILL
        styled_row(next_row, 2, tc + [sum(tc)], TC_FILL, bold=True)
        next_row += 1

        # FTE Risk
        tr = [totals["risk_by_month"].get(m["key"], 0.0) for m in months]
        ws.cell(next_row, 1, "FTE Risk").font = Font(bold=True)
        ws.cell(next_row, 1).fill = RK_FILL
        styled_row(next_row, 2, tr + [sum(tr)], RK_FILL, bold=True)
        next_row += 1

        # Utilisation %
        tu = [totals["utilisation_by_month"].get(m["key"], 0.0) for m in months]
        ws.cell(next_row, 1, "Utilisation %").font = Font(bold=True, italic=True)
        for ci, v in enumerate(tu, 2):
            c = ws.cell(next_row, ci, f"{v:.2f}%")
            c.alignment = CENTER
        ws.cell(next_row, total_col, "")

        # Column widths
        ws.column_dimensions["A"].width = 26
        for ci in range(2, total_col + 1):
            ws.column_dimensions[get_column_letter(ci)].width = 13

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()


# ---------------------------------------------------------------------------
# Private helpers used by get_data
# ---------------------------------------------------------------------------

def _totals_by_month(demand_fte: dict, months_order: list) -> dict:
    """Sum all category FTEs per month."""
    by_month: dict = {}
    for cat_data in demand_fte.values():
        for mkey, fte in cat_data.items():
            by_month[mkey] = by_month.get(mkey, 0.0) + fte
    return {k: _r2(by_month.get(k, 0.0)) for k in months_order}


def _risk_util(demand_by_month: dict, cap_fte: dict, months_order: list):
    """Return (risk_by_month, utilisation_by_month) dicts."""
    risk: dict = {}
    util: dict = {}
    for mkey in months_order:
        d = demand_by_month.get(mkey, 0.0)
        c = cap_fte.get(mkey, 0.0)
        risk[mkey] = _r2(c - d)
        util[mkey] = _r2(d / c * 100) if c else 0.0
    return risk, util


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REPORT_REGISTRY = {
    "demand-capacity": DemandCapacityService,
}
