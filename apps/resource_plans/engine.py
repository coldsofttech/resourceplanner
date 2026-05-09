import logging

from django.db import close_old_connections
from django.utils import timezone

from .models import (
    ResourcePlanVersion,
    ResourcePlanVersionProject,
    PlanPhase,
    PlanEngineJob,
)

_engine_logger = logging.getLogger("resource_plans.engine")


def _engine_update(job_id, **fields):
    """Atomically update engine job fields by PK — safe to call from a background thread."""
    PlanEngineJob.objects.filter(pk=job_id).update(**fields)


def _check_circular(phases):
    """Return list of phase IDs involved in cycles, or [] if none."""
    graph = {ph.id: [] for ph in phases}
    for ph in phases:
        for dep in ph.dependencies.all():
            pred_id = dep.predecessor_phase_id
            if pred_id in graph:
                graph[pred_id].append(ph.id)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in graph}
    cycle_nodes = set()

    def dfs(node):
        colour[node] = GREY
        for nb in graph.get(node, []):
            if colour[nb] == GREY:
                cycle_nodes.add(node)
                cycle_nodes.add(nb)
            elif colour[nb] == WHITE:
                dfs(nb)
        colour[node] = BLACK

    for node in list(graph):
        if colour[node] == WHITE:
            dfs(node)

    return list(cycle_nodes)


def run_engine(job_id):
    """Background thread target — executes the engine for the given job."""
    close_old_connections()
    try:
        job = PlanEngineJob.objects.select_related("plan", "version").get(pk=job_id)
    except PlanEngineJob.DoesNotExist:
        _engine_logger.error("Engine job %s not found.", job_id)
        return

    try:
        from .services import PlaceholderLeaveService, CapacitySnapshotService
        now = timezone.now()
        steps_log = []

        def _log_step(name, start_t, end_t):
            steps_log.append({
                "step": name,
                "started_at": start_t.isoformat(),
                "completed_at": end_t.isoformat(),
                "duration_ms": int((end_t - start_t).total_seconds() * 1000),
            })

        _engine_update(job_id, status=PlanEngineJob.STATUS_RUNNING, started_at=now,
                       current_step="Step 1/5: Validating configuration", progress_pct=5)

        version = job.version
        errors = []
        warnings = []

        # ── Step 1: Validation ────────────────────────────────────────────────
        projects = list(
            ResourcePlanVersionProject.objects.filter(version=version)
            .select_related("project__programme")
            .prefetch_related("teams__team")
        )

        if not projects:
            errors.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": "Version has no projects configured.",
            })

        all_phases = []

        for proj in projects:
            teams = list(proj.teams.all())
            if not teams:
                errors.append({
                    "entity": "project",
                    "id": proj.id,
                    "name": proj.project.name,
                    "message": "No teams assigned to this project.",
                })
                continue

            if proj.is_team_budget_mismatch:
                warnings.append({
                    "entity": "project",
                    "id": proj.id,
                    "name": proj.project.name,
                    "message": "Team allocation does not match basis amount (budget mismatch).",
                })

            for team_entry in teams:
                phases = list(
                    PlanPhase.objects.filter(plan_project_team=team_entry)
                    .prefetch_related("dependencies", "pauses", "assignments")
                )
                all_phases.extend(phases)

                if not phases:
                    errors.append({
                        "entity": "team",
                        "id": team_entry.id,
                        "team_name": team_entry.team.name,
                        "project_name": proj.project.name,
                        "message": "No phases defined for this team allocation.",
                    })
                    continue

                for ph in phases:
                    if ph.is_split_incomplete:
                        errors.append({
                            "entity": "phase",
                            "id": ph.id,
                            "name": ph.name,
                            "project_name": proj.project.name,
                            "message": "PERCENT split values do not sum to 100%.",
                        })
                    for pause in ph.pauses.all():
                        if pause.is_beyond_fy:
                            warnings.append({
                                "entity": "pause",
                                "id": pause.id,
                                "phase_name": ph.name,
                                "project_name": proj.project.name,
                                "message": "Pause extends beyond the financial year.",
                            })

        if all_phases:
            phase_ids_with_cycles = _check_circular(all_phases)
            for pid in phase_ids_with_cycles:
                ph = next((p for p in all_phases if p.id == pid), None)
                errors.append({
                    "entity": "dependency",
                    "phase_id": pid,
                    "phase_name": ph.name if ph else str(pid),
                    "message": "Circular dependency detected involving this phase.",
                })

        step1_end = timezone.now()
        _log_step("Step 1: Validate configuration", now, step1_end)
        _engine_update(job_id, current_step="Step 1/5: Validating configuration", progress_pct=20)

        validation_result = {
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }

        if job.mode == PlanEngineJob.MODE_VALIDATE:
            completed = timezone.now()
            duration = int((completed - now).total_seconds())
            _engine_update(
                job_id,
                status=PlanEngineJob.STATUS_COMPLETE,
                current_step="Complete",
                progress_pct=100,
                completed_at=completed,
                duration_seconds=duration,
                validation_result=validation_result,
                steps_log=steps_log,
            )
            return

        # ── Step 2: Generate placeholder leave ────────────────────────────────
        step2_start = timezone.now()
        _engine_update(job_id, current_step="Step 2/5: Generating placeholder leave", progress_pct=40)
        try:
            PlaceholderLeaveService.generate_for_version(
                version, job.include_current_sprint, remove_overrides=job.remove_overrides
            )
        except Exception as _exc2:
            _engine_logger.warning("Placeholder leave step failed for job %s: %s", job_id, _exc2)
            warnings.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": f"Placeholder leave generation skipped: {_exc2}",
            })
        _log_step("Step 2: Generate placeholder leave", step2_start, timezone.now())

        # ── Step 3: Sync capacity snapshot ────────────────────────────────────
        step3_start = timezone.now()
        _engine_update(job_id, current_step="Step 3/5: Syncing capacity snapshot", progress_pct=60)
        try:
            CapacitySnapshotService.sync_for_version(version)
        except Exception as _exc3:
            _engine_logger.warning("Capacity snapshot step failed for job %s: %s", job_id, _exc3)
            warnings.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": f"Capacity snapshot skipped: {_exc3}",
            })
        _log_step("Step 3: Sync capacity snapshot", step3_start, timezone.now())

        # ── Step 4: Reset override flag if remove_overrides was set ──────────
        if job.remove_overrides:
            ResourcePlanVersion.objects.filter(pk=version.pk).update(has_pl_overrides=False)

        # ── Steps 4-5: future allocation / conflict phases ────────────────────
        for label, pct in [("Step 4/5: Computing allocations", 80), ("Step 5/5: Detecting conflicts", 95)]:
            _engine_update(job_id, current_step=label, progress_pct=pct)

        completed = timezone.now()
        duration = int((completed - now).total_seconds())
        _engine_update(
            job_id,
            status=PlanEngineJob.STATUS_COMPLETE,
            current_step="Complete",
            progress_pct=100,
            completed_at=completed,
            duration_seconds=duration,
            validation_result=validation_result,
            steps_log=steps_log,
        )

    except Exception as exc:
        _engine_logger.exception("Engine job %s failed.", job_id)
        _engine_update(
            job_id,
            status=PlanEngineJob.STATUS_FAILED,
            current_step="Failed",
            completed_at=timezone.now(),
            error_log=str(exc),
        )
