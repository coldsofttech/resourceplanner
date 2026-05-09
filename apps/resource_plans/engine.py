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
        from .services import (
            PlaceholderLeaveService,
            CapacitySnapshotService,
            AllocationEngineService,
        )
        now = timezone.now()
        steps_log = []

        def _log_step(name, start_t, end_t, result="completed"):
            steps_log.append({
                "step": name,
                "result": result,
                "started_at": start_t.isoformat(),
                "completed_at": end_t.isoformat(),
                "duration_ms": int((end_t - start_t).total_seconds() * 1000),
            })

        _engine_update(job_id, status=PlanEngineJob.STATUS_RUNNING, started_at=now,
                       current_step="Step 1/7: Validating configuration", progress_pct=5)

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
        _engine_update(job_id, current_step="Step 1/7: Validating configuration", progress_pct=15)

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

        # ── Step 2: Override placeholder leaves (skip if remove_overrides not set) ──
        step2_start = timezone.now()
        if job.remove_overrides:
            _engine_update(
                job_id,
                current_step="Step 2/7: Overriding placeholder leaves",
                progress_pct=22,
            )
            try:
                PlaceholderLeaveService.clear_overrides_for_version(version)
                ResourcePlanVersion.objects.filter(pk=version.pk).update(has_pl_overrides=False)
                step2_result = "completed"
            except Exception as _exc2:
                _engine_logger.warning("Override PL step failed for job %s: %s", job_id, _exc2)
                warnings.append({
                    "entity": "version",
                    "id": version.id,
                    "name": f"v{version.version}",
                    "message": f"Override placeholder leaves failed: {_exc2}",
                })
                step2_result = "failed"
        else:
            _engine_update(
                job_id,
                current_step="Step 2/7: Overriding placeholder leaves",
                progress_pct=22,
            )
            step2_result = "skipped"
        _log_step("Step 2: Override placeholder leaves", step2_start, timezone.now(), result=step2_result)

        # ── Step 3: Generate placeholder leave ────────────────────────────────
        step3_start = timezone.now()
        _engine_update(job_id, current_step="Step 3/7: Generating placeholder leave", progress_pct=35)
        try:
            PlaceholderLeaveService.generate_for_version(
                version, job.include_current_sprint, remove_overrides=False
            )
            step3_result = "completed"
        except Exception as _exc3:
            _engine_logger.warning("Placeholder leave step failed for job %s: %s", job_id, _exc3)
            warnings.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": f"Placeholder leave generation failed: {_exc3}",
            })
            step3_result = "failed"
        _log_step("Step 3: Generate placeholder leave", step3_start, timezone.now(), result=step3_result)

        # ── Step 4: Sync capacity snapshot ────────────────────────────────────
        step4_start = timezone.now()
        _engine_update(job_id, current_step="Step 4/7: Syncing capacity snapshot", progress_pct=50)
        try:
            CapacitySnapshotService.sync_for_version(version)
            step4_result = "completed"
        except Exception as _exc4:
            _engine_logger.warning("Capacity snapshot step failed for job %s: %s", job_id, _exc4)
            warnings.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": f"Capacity snapshot failed: {_exc4}",
            })
            step4_result = "failed"
        _log_step("Step 4: Sync capacity snapshot", step4_start, timezone.now(), result=step4_result)

        # ── Step 5: Build dependency graph ────────────────────────────────────
        step5_start = timezone.now()
        _engine_update(job_id, current_step="Step 5/7: Building dependency graph", progress_pct=62)
        _log_step("Step 5: Build dependency graph", step5_start, timezone.now(), result="completed")

        # ── Step 6: Compute allocations ───────────────────────────────────────
        step6_start = timezone.now()
        _engine_update(job_id, current_step="Step 6/7: Computing allocations", progress_pct=75)
        alloc_set = None
        conflicts = []
        try:
            alloc_set, conflicts = AllocationEngineService.run(job)
            step6_result = "completed"
        except Exception as _exc6:
            _engine_logger.warning("Allocation engine failed for job %s: %s", job_id, _exc6)
            warnings.append({
                "entity": "version",
                "id": version.id,
                "name": f"v{version.version}",
                "message": f"Allocation engine failed: {_exc6}",
            })
            step6_result = "failed"
        _log_step("Step 6: Compute allocations", step6_start, timezone.now(), result=step6_result)

        # ── Step 7: Detect and persist conflicts ──────────────────────────────
        step7_start = timezone.now()
        _engine_update(job_id, current_step="Step 7/7: Detecting conflicts", progress_pct=92)
        persisted_conflicts = []
        if alloc_set:
            try:
                from .services import ConflictDetectionService
                persisted_conflicts = ConflictDetectionService.detect_and_persist(
                    version, alloc_set, job
                )
            except Exception as _exc7:
                _engine_logger.warning("Conflict detection failed for job %s: %s", job_id, _exc7)

        error_conflicts = [c for c in persisted_conflicts if c.severity == 'ERROR']
        conflict_dicts = [
            {
                'id': c.id,
                'conflict_type': c.conflict_type,
                'severity': c.severity,
                'status': c.status,
                'description': c.description,
                'affected_sprint': c.affected_sprint_id,
                'affected_member': c.affected_team_member_id,
                'affected_project': c.affected_project_id,
            }
            for c in persisted_conflicts
        ]
        _log_step("Step 7: Detect conflicts", step7_start, timezone.now(), result="completed")

        validation_result["conflicts"] = conflict_dicts
        validation_result["conflict_count"] = len(persisted_conflicts)
        validation_result["error_conflict_count"] = len(error_conflicts)
        if alloc_set:
            validation_result["allocation_set_id"] = alloc_set.id

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
