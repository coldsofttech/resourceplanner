"""
Resource Plan — Allocation Engine
==================================
Pseudocode expressed as structured Python.
No Django ORM calls are made — all DB interaction is represented as
descriptive function calls (e.g. db.get_*, db.save_*, db.delete_*).
All business logic is here; DB layer is a thin adapter in practice.

Engine phases
─────────────
1. VALIDATE          — structural integrity checks
2. PLACEHOLDERS      — projected leave generation
3. CAPACITY TABLES   — gross / absence / net capacity per engineer per sprint
4. DEPENDENCY GRAPH  — topological sort of all phases across all projects
5. ALLOCATE          — phase-by-phase allocation respecting all rules
6. REBALANCE         — utilisation maximisation pass
7. CONFLICTS         — threshold breach + ramp-down candidate detection
8. UTILISATION       — team and member utilisation summaries
9. AUDIT             — single engine-run audit entry
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_UP
from collections import deque
from typing import Optional
import math


# ── Constants (resolved from configurations app at runtime) ───────────────────
SPRINT_DURATION_DAYS            = Decimal('10')
STORY_POINT_PRICE               = Decimal('500')   # £ per day
PLACEHOLDER_FORCE_WINDOW        = 3                # sprints
REBALANCE_THRESHOLD_PCT         = Decimal('70')    # below this → try to fill
RAMPDOWN_THRESHOLD_PCT          = Decimal('50')    # below this → flag ramp-down
ALLOCATION_THRESHOLD_PCT        = Decimal('10')    # over/under days_required


# ── Helpers ───────────────────────────────────────────────────────────────────

def ceil_quarter(value: Decimal) -> Decimal:
    """Ceiling to nearest 0.25."""
    return (value * 4).to_integral_value(rounding=ROUND_UP) / 4


def ceil_half(value: Decimal) -> Decimal:
    """Ceiling to nearest 0.5."""
    return (value * 2).to_integral_value(rounding=ROUND_UP) / 2


def utilisation_pct(allocated: Decimal, net_capacity: Decimal) -> Decimal:
    if net_capacity <= 0:
        return Decimal('100')
    return (allocated / net_capacity * 100).quantize(Decimal('0.01'))


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class EngineerState:
    """Live mutable state for one engineer during engine run."""
    team_member_id: int
    team_id: int
    # sprint_id → remaining net capacity (updated as allocation is written)
    remaining: dict[int, Decimal] = field(default_factory=dict)
    # sprint_id → total allocated days across all projects
    allocated: dict[int, Decimal] = field(default_factory=dict)

    def total_allocated(self) -> Decimal:
        return sum(self.allocated.values())

    def total_remaining(self) -> Decimal:
        return sum(self.remaining.values())

    def utilisation(self, net_capacity_map: dict[int, Decimal]) -> Decimal:
        total_net = sum(net_capacity_map.get(s, Decimal('0'))
                        for s in net_capacity_map)
        return utilisation_pct(self.total_allocated(), total_net)


@dataclass
class PhaseNode:
    """Phase with resolved metadata for engine processing."""
    phase_id: int
    plan_project_id: int
    project_id: int
    team_id: int
    assignment_ids: list[int]
    auto_assign: bool
    allow_multiple: bool
    split_mode: str
    ramp_pattern: str
    segments: list[dict]           # ordered segment dicts
    pauses: list[dict]             # pause windows [{from_sprint, resume_sprint}]
    start_sprint_id: Optional[int]
    end_sprint_id: Optional[int]
    dates_strict: bool
    max_days_per_sprint: Optional[Decimal]
    sequence_order: int
    days_required: Decimal         # from ResourcePlanProjectTeam.allocated_days
    dependencies: list[dict]       # [{predecessor_phase_id, type, lag_sprints}]
    # Resolved after topological sort
    earliest_start_sprint_id: Optional[int] = None
    # Set during allocation
    allocated_days: Decimal = Decimal('0')
    finish_sprint_id: Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_engine(plan_id: int, mode: str, include_current_sprint: bool) -> dict:
    """
    Main engine entry point.
    mode: 'VALIDATE' | 'FULL'
    Returns summary dict written to ResourcePlanEngineJob.
    """

    # ── Initialise job ────────────────────────────────────────────────────────
    job = db.create_engine_job(
        plan_id=plan_id,
        mode=mode,
        include_current_sprint=include_current_sprint,
    )
    db.mark_job_started(job.id)

    try:
        plan        = db.get_plan(plan_id)
        scope       = db.get_scope(plan.plan_group)
        fy          = db.get_financial_year(scope.financial_year_id)
        all_sprints = db.get_fy_sprints(fy.id)          # ordered list
        today_sprint= db.get_current_sprint(fy.id)

        # Sprint range the engine may touch
        active_sprints = resolve_active_sprints(
            all_sprints, today_sprint, include_current_sprint
        )

        # ── Phase 1: Validation ───────────────────────────────────────────────
        db.update_job_step(job.id, 'Step 1/9: Validating plan configuration', 5)
        validation_result = run_validation(plan, scope, fy, active_sprints)

        if validation_result['has_errors']:
            db.save_validation_result(job.id, validation_result)
            db.mark_job_complete(job.id, status='COMPLETE')
            return {'status': 'COMPLETE', 'mode': 'VALIDATE',
                    'validation': validation_result}

        if mode == 'VALIDATE':
            db.save_validation_result(job.id, validation_result)
            db.mark_job_complete(job.id, status='COMPLETE')
            return {'status': 'COMPLETE', 'mode': 'VALIDATE',
                    'validation': validation_result}

        # ── Full run from here ────────────────────────────────────────────────

        # ── Phase 2: Placeholder leave ────────────────────────────────────────
        db.update_job_step(job.id, 'Step 2/9: Generating placeholder leave', 15)
        generate_placeholder_leave(plan, fy, all_sprints, active_sprints, job)

        # ── Phase 3: Capacity tables ──────────────────────────────────────────
        db.update_job_step(job.id, 'Step 3/9: Building capacity tables', 30)
        engineer_states = build_capacity_tables(plan, fy, active_sprints, job)

        # ── Phase 4: Dependency graph + ordering ──────────────────────────────
        db.update_job_step(job.id, 'Step 4/9: Resolving phase dependencies', 40)
        ordered_phases = build_phase_execution_order(plan, active_sprints)

        # ── Phase 5: Allocation ───────────────────────────────────────────────
        db.update_job_step(job.id, 'Step 5/9: Allocating phases', 55)
        allocation_set = db.create_allocation_set(plan_id=plan.id, job_id=job.id)
        conflicts      = []

        allocate_all_phases(
            ordered_phases, engineer_states,
            active_sprints, allocation_set, plan, job, conflicts
        )

        # ── Phase 6: Rebalance ────────────────────────────────────────────────
        db.update_job_step(job.id, 'Step 6/9: Rebalancing utilisation', 70)
        rebalance_utilisation(
            engineer_states, allocation_set, active_sprints,
            ordered_phases, job, conflicts
        )

        # ── Phase 7: Conflict detection (threshold + ramp-down) ───────────────
        db.update_job_step(job.id, 'Step 7/9: Detecting threshold conflicts', 80)
        detect_threshold_conflicts(plan, allocation_set, ordered_phases, conflicts)
        detect_rampdown_candidates(engineer_states, active_sprints,
                                   allocation_set, conflicts)
        db.save_conflicts(allocation_set.id, job.id, conflicts)

        # ── Phase 8: Utilisation summaries ────────────────────────────────────
        db.update_job_step(job.id, 'Step 8/9: Computing utilisation', 90)
        compute_utilisation_summaries(
            engineer_states, allocation_set, active_sprints, job
        )

        # ── Phase 9: Audit ────────────────────────────────────────────────────
        db.update_job_step(job.id, 'Step 9/9: Writing audit log', 98)
        db.write_audit_log(
            plan_id       = plan.id,
            event_type    = 'ENGINE_RUN',
            entity_type   = 'ResourcePlanEngineJob',
            entity_id     = job.id,
            after_state   = {
                'mode'            : mode,
                'sprints_in_scope': len(active_sprints),
                'phases_allocated': len(ordered_phases),
                'conflicts_raised': len(conflicts),
                'allocation_set'  : allocation_set.id,
            }
        )

        db.mark_job_complete(job.id, status='COMPLETE', progress=100)
        return {
            'status'        : 'COMPLETE',
            'allocation_set': allocation_set.id,
            'conflicts'     : len(conflicts),
        }

    except Exception as exc:
        db.mark_job_failed(job.id, error=str(exc))
        raise


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def run_validation(plan, scope, fy, active_sprints) -> dict:
    """
    Structural validation before any writes.
    Returns {has_errors, errors, warnings} dict.
    Errors block the run. Warnings surface to user but do not block.
    """
    errors   = []
    warnings = []

    def err(level, entity_type, entity_id, message):
        target = errors if level == 'error' else warnings
        target.append({'entity_type': entity_type,
                        'entity_id'  : entity_id,
                        'message'    : message})

    # Plan level
    if plan.status not in ('DRAFT', 'ACTIVE'):
        err('error', 'ResourcePlan', plan.id,
            f'Plan status is {plan.status}. Only DRAFT or ACTIVE plans can be run.')

    plan_projects = db.get_plan_projects(plan.id)
    if not plan_projects:
        err('error', 'ResourcePlan', plan.id, 'Plan has no projects configured.')

    for pp in plan_projects:

        # Project level
        if pp.days_required <= 0:
            err('error', 'ResourcePlanProject', pp.id,
                f'Project {pp.project_id} has days_required = 0. Check basis_amount and STORY_POINT_PRICE.')

        if not pp.basis_amount:
            err('error', 'ResourcePlanProject', pp.id,
                f'Project {pp.project_id} has no basis_amount set.')

        if pp.budget_release_mode:
            releases     = db.get_budget_releases(pp.id)
            release_sum  = sum(r.amount for r in releases)
            if release_sum > pp.basis_amount:
                err('error', 'ResourcePlanProject', pp.id,
                    f'Budget releases ({release_sum}) exceed basis_amount ({pp.basis_amount}).')

        # Team assignment level
        project_teams = db.get_project_teams(pp.id)
        if not project_teams:
            err('error', 'ResourcePlanProject', pp.id,
                f'Project {pp.project_id} has no teams assigned.')

        percent_teams = [t for t in project_teams if t.allocation_type == 'PERCENT']
        if percent_teams:
            pct_sum = sum(t.allocation_pct for t in percent_teams)
            if pct_sum != 100:
                err('error', 'ResourcePlanProjectTeam', pp.id,
                    f'PERCENT allocations sum to {pct_sum}%, must be 100%.')

        budget_teams = [t for t in project_teams if t.allocation_type == 'BUDGET']
        if budget_teams:
            budget_sum = sum(t.allocation_budget for t in budget_teams)
            if budget_sum != pp.basis_amount:
                err('warning', 'ResourcePlanProjectTeam', pp.id,
                    f'Team budgets sum ({budget_sum}) does not match basis_amount ({pp.basis_amount}).')

        for pt in project_teams:

            # Phase level
            phases = db.get_phases(pt.id)
            if not phases:
                err('error', 'ResourcePlanProjectTeam', pt.id,
                    f'Team {pt.team_id} on project {pp.project_id} has no phases.')

            for phase in phases:
                segments = db.get_segments(phase.id)
                if not segments:
                    err('error', 'ResourcePlanPhase', phase.id,
                        f'Phase {phase.name} has no segments defined.')

                assignments = db.get_assignments(phase.id)
                has_auto    = any(a.auto_assign for a in assignments)
                has_manual  = any(not a.auto_assign for a in assignments)
                if not has_auto and not has_manual:
                    err('error', 'ResourcePlanPhase', phase.id,
                        f'Phase {phase.name} has no assignments configured.')

                # INTERIM assignments must have replaces_member
                for a in assignments:
                    if a.assignment_type == 'INTERIM' and not a.replaces_member_id:
                        err('error', 'ResourcePlanAssignment', a.id,
                            f'INTERIM assignment in phase {phase.name} has no replaces_member set.')

                # PERCENT split must sum to 100
                pct_assignments = [a for a in assignments
                                   if not a.auto_assign and phase.split_mode == 'PERCENT']
                if pct_assignments:
                    split_sum = sum(a.split_value or 0 for a in pct_assignments)
                    if split_sum != 100:
                        err('warning', 'ResourcePlanPhase', phase.id,
                            f'Phase {phase.name} PERCENT splits sum to {split_sum}%, expected 100%.')

                # Dependency circular check
                deps = db.get_phase_dependencies(phase.id)
                for dep in deps:
                    if has_circular_dependency(phase.id, dep.predecessor_phase_id):
                        err('error', 'ResourcePlanPhaseDependency', phase.id,
                            f'Circular dependency detected involving phase {phase.name}.')

                # Pauses within FY
                pauses = db.get_phase_pauses(phase.id)
                for pause in pauses:
                    if pause.is_beyond_fy:
                        err('warning', 'ResourcePlanPhasePause', pause.id,
                            f'Pause in phase {phase.name} extends beyond FY boundary.')

    # Engine should not modify past sprints
    if not active_sprints:
        err('error', 'ResourcePlan', plan.id,
            'No active sprints in scope. FY may be complete.')

    return {
        'has_errors': len(errors) > 0,
        'errors'    : errors,
        'warnings'  : warnings,
    }


def has_circular_dependency(phase_id: int, predecessor_id: int) -> bool:
    """
    Walk the dependency graph from predecessor_id.
    If we reach phase_id again, there is a cycle.
    Uses BFS.
    """
    visited = set()
    queue   = deque([predecessor_id])
    while queue:
        current = queue.popleft()
        if current == phase_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        for dep in db.get_phase_dependencies(current):
            queue.append(dep.predecessor_phase_id)
    return False


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — PLACEHOLDER LEAVE
# ══════════════════════════════════════════════════════════════════════════════

def generate_placeholder_leave(plan, fy, all_sprints, active_sprints, job):
    """
    Generate projected leave placeholders for all engineers in scope.

    Formula:
      placeholder_days = entitlement
                         - past_leave_days (within FY, before today)
                         - upcoming_leave_days (within FY, from today)

    Distribution:
      - Second half of active_sprints only
      - Skip sprints that already have confirmed leave
        UNLESS fewer than PLACEHOLDER_FORCE_WINDOW sprints remain
          in the second half
      - Cap each sprint at net capacity for that engineer
    """

    # Clean up previous engine-generated placeholders
    db.delete_engine_placeholder_leaves(plan.id)

    team_members = db.get_all_plan_members(plan.id)

    for member in team_members:

        entitlement       = db.get_holiday_entitlement(member.id, fy.id)
        past_leave_days   = db.sum_leave_days(member.id, fy.start_date,
                                              db.today(), confirmed_only=True)
        upcoming_leaves   = db.get_upcoming_leaves(member.id, fy.id)
        upcoming_days     = sum(l.days for l in upcoming_leaves)
        placeholder_total = entitlement - past_leave_days - upcoming_days

        if placeholder_total <= 0:
            continue

        # Second half of active sprints
        mid              = len(active_sprints) // 2
        second_half      = active_sprints[mid:]
        sprints_with_leave = {
            l.sprint_id for l in upcoming_leaves
        }

        # Identify which sprints to allocate into
        available_sprints = [
            s for s in second_half
            if s.id not in sprints_with_leave
        ]

        # Force window: if few sprints remain, stop skipping leave sprints
        remaining_count = len(second_half)
        if remaining_count <= PLACEHOLDER_FORCE_WINDOW:
            available_sprints = second_half  # include leave sprints

        if not available_sprints:
            available_sprints = second_half  # fallback

        # Distribute evenly across available sprints
        n             = len(available_sprints)
        raw_per_sprint = placeholder_total / n
        days_per_sprint = ceil_half(raw_per_sprint)

        remaining_to_allocate = placeholder_total

        for sprint in available_sprints:
            if remaining_to_allocate <= 0:
                break

            # Cap at sprint net capacity
            net_capacity  = db.get_net_capacity(plan.id, member.id, sprint.id)
            days_this_sprint = min(days_per_sprint, net_capacity,
                                   remaining_to_allocate)
            days_this_sprint = ceil_half(days_this_sprint)

            if days_this_sprint <= 0:
                continue

            db.save_placeholder_leave(
                plan_id       = plan.id,
                team_member_id= member.id,
                sprint_id     = sprint.id,
                days          = days_this_sprint,
                engine_job_id = job.id,
            )
            remaining_to_allocate -= days_this_sprint


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — CAPACITY TABLES
# ══════════════════════════════════════════════════════════════════════════════

def build_capacity_tables(plan, fy, active_sprints, job) -> dict[int, EngineerState]:
    """
    Regenerate ResourcePlanCapacity, ResourcePlanAbsence,
    ResourcePlanNetCapacity for all engineers × active sprints.

    Returns engineer_states: {team_member_id → EngineerState}
    used as the live mutable state during allocation.
    """

    # Clean previous capacity rows for this plan
    db.delete_capacity_tables(plan.id)

    team_members   = db.get_all_plan_members(plan.id)
    engineer_states = {}

    for member in team_members:

        state = EngineerState(
            team_member_id=member.id,
            team_id=member.team_id,
        )

        for sprint in active_sprints:

            # ── Gross capacity ────────────────────────────────────────────────
            total_days = SPRINT_DURATION_DAYS
            db.save_capacity(plan.id, member.id, sprint.id, total_days, job.id)

            # ── Absences ──────────────────────────────────────────────────────
            holiday_days = db.get_public_holiday_days(
                member.office_location_id, sprint.id
            )
            leave_days = db.get_confirmed_leave_days(member.id, sprint.id)

            if holiday_days > 0:
                db.save_absence(plan.id, member.id, sprint.id,
                                'HOLIDAY', holiday_days,
                                source_holiday_ids=db.get_holiday_ids(
                                    member.office_location_id, sprint.id),
                                job_id=job.id)

            if leave_days > 0:
                db.save_absence(plan.id, member.id, sprint.id,
                                'LEAVE', leave_days,
                                source_leave_ids=db.get_leave_ids(
                                    member.id, sprint.id),
                                job_id=job.id)

            # ── Placeholder leave ─────────────────────────────────────────────
            placeholder_days = db.get_placeholder_leave_days(
                plan.id, member.id, sprint.id
            )

            # ── Net capacity ──────────────────────────────────────────────────
            absence_days = holiday_days + leave_days
            net_days     = total_days - absence_days - placeholder_days
            is_negative  = net_days < 0

            db.save_net_capacity(
                plan_id          = plan.id,
                team_member_id   = member.id,
                sprint_id        = sprint.id,
                total_days       = total_days,
                absence_days     = absence_days,
                placeholder_days = placeholder_days,
                net_days         = max(net_days, Decimal('0')),
                is_negative      = is_negative,
                job_id           = job.id,
            )

            # Populate live state
            effective_net          = max(net_days, Decimal('0'))
            state.remaining[sprint.id] = effective_net
            state.allocated[sprint.id] = Decimal('0')

        engineer_states[member.id] = state

        # ── Placeholder engineer capacity ─────────────────────────────────────
        # Same pattern for placeholder engineers
        placeholder_engineers = db.get_placeholder_engineers(plan.id)
        for pe in placeholder_engineers:
            pe_state = EngineerState(
                team_member_id=None,
                team_id=pe.team_id,
            )
            for sprint in active_sprints:
                if sprint.position < pe.onboard_sprint.position:
                    pe_state.remaining[sprint.id] = Decimal('0')
                    pe_state.allocated[sprint.id] = Decimal('0')
                    continue

                absence_days = db.get_placeholder_engineer_absence(
                    pe.id, sprint.id
                )
                net = pe.capacity_days_per_sprint - absence_days
                net = max(net, Decimal('0'))
                pe_state.remaining[sprint.id] = net
                pe_state.allocated[sprint.id] = Decimal('0')

            engineer_states[f'pe_{pe.id}'] = pe_state

    return engineer_states


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — DEPENDENCY GRAPH + ORDERING
# ══════════════════════════════════════════════════════════════════════════════

def build_phase_execution_order(plan, active_sprints) -> list[PhaseNode]:
    """
    1. Load all phases across all projects in the plan
    2. Apply primary sort key: effective_priority, dates_strict,
       confidence, end_sprint, display_order
    3. Build dependency graph
    4. Topological sort (Kahn's algorithm)
    5. Return ordered list of PhaseNode ready for allocation
    """

    all_phases = db.get_all_plan_phases(plan.id)
    phase_nodes = {}

    for phase in all_phases:
        pp  = db.get_plan_project_for_phase(phase.id)
        ppt = db.get_plan_project_team_for_phase(phase.id)

        node = PhaseNode(
            phase_id        = phase.id,
            plan_project_id = pp.id,
            project_id      = pp.project_id,
            team_id         = ppt.team_id,
            assignment_ids  = [a.id for a in db.get_assignments(phase.id)],
            auto_assign     = any(a.auto_assign for a in db.get_assignments(phase.id)),
            allow_multiple  = phase.allow_multiple_engineers,
            split_mode      = phase.split_mode,
            ramp_pattern    = phase.ramp_pattern,
            segments        = [s.__dict__ for s in db.get_segments(phase.id)],
            pauses          = [p.__dict__ for p in db.get_phase_pauses(phase.id)],
            start_sprint_id = phase.start_sprint_id or pp.start_sprint_id,
            end_sprint_id   = phase.end_sprint_id or pp.end_sprint_id,
            dates_strict    = pp.dates_strict,
            max_days_per_sprint = phase.max_days_per_sprint,
            sequence_order  = phase.sequence_order,
            days_required   = ppt.allocated_days,
            dependencies    = [
                {
                    'predecessor_phase_id': d.predecessor_phase_id,
                    'type'               : d.dependency_type,
                    'lag_sprints'        : d.lag_sprints,
                }
                for d in db.get_phase_dependencies(phase.id)
            ],
        )

        # If no start/end sprint at all, infer from plan FY
        if not node.start_sprint_id:
            node.start_sprint_id = active_sprints[0].id
        if not node.end_sprint_id:
            node.end_sprint_id = active_sprints[-1].id

        phase_nodes[phase.id] = node

    # ── Priority sort key ─────────────────────────────────────────────────────
    PRIORITY_RANK   = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    CONFIDENCE_RANK = {'VERY_HIGH': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}

    def sort_key(node: PhaseNode):
        pp            = db.get_plan_project(node.plan_project_id)
        eff_priority  = pp.effective_priority
        eff_confidence= pp.effective_confidence
        return (
            0 if pp.dates_strict else 1,              # dates_strict first
            PRIORITY_RANK.get(eff_priority, 99),      # priority
            CONFIDENCE_RANK.get(eff_confidence, 99),  # confidence
            node.end_sprint_id or 9999,               # tightest deadline
            pp.display_order,                         # user ordering
            node.sequence_order,                      # phase sequence
        )

    sorted_nodes = sorted(phase_nodes.values(), key=sort_key)

    # ── Topological sort (Kahn's algorithm) ───────────────────────────────────
    # Build in-degree map
    in_degree = {node.phase_id: 0 for node in sorted_nodes}
    dependents: dict[int, list[int]] = {
        node.phase_id: [] for node in sorted_nodes
    }

    for node in sorted_nodes:
        for dep in node.dependencies:
            pred_id = dep['predecessor_phase_id']
            if pred_id in in_degree:
                in_degree[node.phase_id] += 1
                dependents[pred_id].append(node.phase_id)

    # Kahn's BFS — use priority queue seeded from sorted_nodes order
    # to preserve priority ordering within dependency-free tiers
    ready_queue = deque([
        node for node in sorted_nodes
        if in_degree[node.phase_id] == 0
    ])
    execution_order = []

    while ready_queue:
        node = ready_queue.popleft()
        execution_order.append(node)

        # Resolve earliest_start based on predecessor finish
        resolve_earliest_start(node, phase_nodes, execution_order)

        for dependent_id in dependents[node.phase_id]:
            in_degree[dependent_id] -= 1
            if in_degree[dependent_id] == 0:
                dep_node = phase_nodes[dependent_id]
                # Insert in priority order into queue
                insert_sorted(ready_queue, dep_node, sort_key)

    if len(execution_order) != len(phase_nodes):
        # Residual cycle — validation should have caught this
        # Record as conflict and skip remaining phases
        pass

    return execution_order


def resolve_earliest_start(node: PhaseNode, phase_nodes: dict,
                            completed: list[PhaseNode]):
    """
    Given node's dependencies, compute the earliest sprint it can start.
    Adjusts for lag/lead and dependency type (SS/FS/FF/SF).
    Also adjusts for pauses (pauses extend effective phase duration).
    """
    if not node.dependencies:
        # No deps — start at configured start_sprint
        node.earliest_start_sprint_id = node.start_sprint_id
        return

    earliest = node.start_sprint_id

    for dep in node.dependencies:
        pred_id   = dep['predecessor_phase_id']
        dep_type  = dep['type']
        lag       = dep['lag_sprints']
        pred_node = phase_nodes.get(pred_id)

        if not pred_node or not pred_node.finish_sprint_id:
            continue

        pred_start_pos  = db.get_sprint_position(pred_node.start_sprint_id)
        pred_finish_pos = db.get_sprint_position(pred_node.finish_sprint_id)

        if dep_type == 'FS':
            # B starts after A finishes + lag
            required_start = pred_finish_pos + 1 + lag
        elif dep_type == 'SS':
            # B starts when A starts + lag
            required_start = pred_start_pos + lag
        elif dep_type == 'FF':
            # B finishes when A finishes + lag
            # Defer — handled at finish resolution
            continue
        elif dep_type == 'SF':
            # B finishes when A starts + lag
            # Defer — handled at finish resolution
            continue
        else:
            continue

        earliest_sprint = db.get_sprint_by_position(required_start)
        if earliest_sprint:
            earliest = max(earliest or earliest_sprint.id,
                           earliest_sprint.id,
                           key=lambda sid: db.get_sprint_position(sid))

    node.earliest_start_sprint_id = earliest or node.start_sprint_id


def insert_sorted(queue: deque, node: PhaseNode, key_fn):
    """Insert node into deque maintaining sort order."""
    items = list(queue)
    items.append(node)
    items.sort(key=key_fn)
    queue.clear()
    queue.extend(items)


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — ALLOCATION
# ══════════════════════════════════════════════════════════════════════════════

def allocate_all_phases(ordered_phases, engineer_states, active_sprints,
                         allocation_set, plan, job, conflicts):
    """
    Iterate phases in topological + priority order.
    For each phase:
      1. Determine eligible sprint range
      2. Build ramp distribution from segments
      3. Select engineers (manual or auto-assign)
      4. Write allocation cells respecting all caps and pauses
      5. Raise conflicts if allocation cannot be completed
    """

    sprint_position = {s.id: i for i, s in enumerate(active_sprints)}
    sprint_by_pos   = {i: s for i, s in enumerate(active_sprints)}

    for node in ordered_phases:

        # ── Determine sprint window for this phase ────────────────────────────
        start_pos = sprint_position.get(node.earliest_start_sprint_id, 0)
        end_pos   = sprint_position.get(node.end_sprint_id,
                                        len(active_sprints) - 1)
        phase_sprints = [
            active_sprints[i] for i in range(start_pos, end_pos + 1)
        ]

        # Remove paused sprints from phase_sprints
        paused_sprint_ids = resolve_paused_sprints(node.pauses, active_sprints)
        effective_sprints = [
            s for s in phase_sprints if s.id not in paused_sprint_ids
        ]

        if not effective_sprints:
            conflicts.append(make_conflict(
                'TIMELINE_BREACH', 'ERROR',
                node, None,
                'Phase has no available sprints after applying pauses.',
            ))
            continue

        # ── Check pause pushes beyond end_sprint ─────────────────────────────
        if paused_sprint_ids and node.dates_strict:
            last_effective = effective_sprints[-1]
            if sprint_position[last_effective.id] > end_pos:
                conflicts.append(make_conflict(
                    'TIMELINE_BREACH', 'WARNING',
                    node, None,
                    'Pauses push phase beyond configured end_sprint.',
                ))

        # ── Budget release caps per sprint ────────────────────────────────────
        sprint_budget_caps = resolve_sprint_budget_caps(
            node.plan_project_id, effective_sprints
        )

        # ── Ramp distribution across effective sprints ────────────────────────
        ramp_days = compute_ramp_distribution(
            node.segments, node.days_required,
            node.max_days_per_sprint, effective_sprints,
            sprint_budget_caps
        )
        # ramp_days: {sprint_id → target_days_for_phase}

        # ── Select engineers for this phase ───────────────────────────────────
        assigned_engineers = resolve_engineers(
            node, engineer_states, effective_sprints, ramp_days, conflicts
        )

        if not assigned_engineers:
            conflicts.append(make_conflict(
                'UNRESOLVABLE_GAP', 'ERROR',
                node, None,
                'No engineers available for phase. Consider manpower request.',
            ))
            db.create_manpower_request(
                allocation_set_id = allocation_set.id,
                team_id           = node.team_id,
                phase_id          = node.phase_id,
                sprints_needed    = len(effective_sprints),
                days_needed       = node.days_required,
            )
            continue

        # ── Write allocation cells ────────────────────────────────────────────
        total_allocated = write_phase_allocations(
            node, assigned_engineers, ramp_days,
            effective_sprints, engineer_states,
            sprint_budget_caps, allocation_set, conflicts
        )

        node.allocated_days   = total_allocated
        node.finish_sprint_id = effective_sprints[-1].id


def resolve_paused_sprints(pauses: list[dict],
                            active_sprints) -> set[int]:
    """Return set of sprint IDs that fall within any pause window."""
    sprint_position = {s.id: i for i, s in enumerate(active_sprints)}
    paused = set()
    for pause in pauses:
        from_pos   = sprint_position.get(pause['pause_from_sprint_id'], -1)
        resume_pos = sprint_position.get(pause['resume_sprint_id'], -1)
        for s in active_sprints:
            pos = sprint_position[s.id]
            if from_pos <= pos < resume_pos:
                paused.add(s.id)
    return paused


def resolve_sprint_budget_caps(plan_project_id: int,
                                 effective_sprints) -> dict[int, Decimal]:
    """
    Return {sprint_id → budget_cap_days} for sprints that have
    explicit budget release entries. Sprints not in the dict are uncapped.
    Month entries are mapped to their constituent sprints equally.
    """
    caps     = {}
    releases = db.get_budget_releases(plan_project_id)

    for release in releases:
        if release.entry_type == 'SPRINT':
            days = ceil_quarter(release.amount / STORY_POINT_PRICE)
            caps[release.sprint_id] = days

        elif release.entry_type == 'MONTH':
            # Find sprints within this calendar month
            month_sprints = [
                s for s in effective_sprints
                if s.month_abbr == release.month
            ]
            if not month_sprints:
                continue
            days_each = ceil_quarter(
                release.amount / STORY_POINT_PRICE / len(month_sprints)
            )
            for s in month_sprints:
                caps[s.id] = days_each

    return caps


def compute_ramp_distribution(segments: list[dict],
                               days_required: Decimal,
                               max_days_per_sprint: Optional[Decimal],
                               effective_sprints: list,
                               budget_caps: dict[int, Decimal],
                               ) -> dict[int, Decimal]:
    """
    Distribute days_required across effective_sprints according to
    the phase's ramp segments.

    Returns {sprint_id → target_days} where target_days is the
    intended allocation for the phase in that sprint (before
    per-engineer split).

    Algorithm:
      1. Map each sprint to a segment based on segment durations
      2. Compute raw pct for that sprint from the segment's
         progression formula
      3. Scale raw pct against max_days_per_sprint (or derived cap)
      4. Normalise so total across all sprints = days_required
      5. Apply budget_caps as hard ceiling per sprint
      6. Re-normalise if budget caps reduce total below days_required
         (remainder spreads to uncapped sprints)
    """

    n = len(effective_sprints)
    if n == 0:
        return {}

    # Effective max per sprint (phase cap or derived from days_required)
    effective_max = max_days_per_sprint or ceil_quarter(
        days_required / n
    )

    # ── Step 1 & 2: assign raw weights per sprint from segments ──────────────
    raw_weights  = {}
    sprint_cursor = 0

    for seg in segments:
        seg_duration   = seg['duration']
        seg_type       = seg['segment_type']   # RAMP or FLAT
        start_pct      = Decimal(str(seg['start_pct'])) / 100
        end_pct        = Decimal(str(seg['end_pct']))   / 100
        progression    = seg['progression']
        step_count     = seg.get('step_count') or 1

        for i in range(seg_duration):
            if sprint_cursor >= n:
                break
            sprint = effective_sprints[sprint_cursor]

            if seg_type == 'FLAT' or start_pct == end_pct:
                weight = start_pct

            elif progression == 'LINEAR':
                if seg_duration == 1:
                    weight = start_pct
                else:
                    t      = i / (seg_duration - 1)
                    weight = start_pct + (end_pct - start_pct) * Decimal(str(t))

            elif progression == 'EXPONENTIAL':
                # Slow start, fast finish: weight = start + (end-start) * t^2
                t      = Decimal(str(i / max(seg_duration - 1, 1)))
                weight = start_pct + (end_pct - start_pct) * (t ** 2)

            elif progression == 'LOGARITHMIC':
                # Fast start, slow finish: weight = start + (end-start) * log(1+t)/log(2)
                import math as _math
                t      = i / max(seg_duration - 1, 1)
                log_w  = _math.log(1 + t) / _math.log(2) if t > 0 else 0
                weight = start_pct + (end_pct - start_pct) * Decimal(str(log_w))

            elif progression == 'STEPPED':
                # Discrete levels
                step_size  = seg_duration / step_count
                step_index = int(i / step_size)
                t          = step_index / max(step_count - 1, 1)
                weight     = start_pct + (end_pct - start_pct) * Decimal(str(t))

            else:
                weight = start_pct

            raw_weights[sprint.id] = weight
            sprint_cursor += 1

        if sprint_cursor >= n:
            break

    # Fill any remaining sprints with last segment's end_pct
    while sprint_cursor < n:
        sprint = effective_sprints[sprint_cursor]
        raw_weights[sprint.id] = end_pct
        sprint_cursor += 1

    # ── Step 3: Scale weights to days ────────────────────────────────────────
    total_weight = sum(raw_weights.values()) or Decimal('1')
    sprint_days  = {}
    for sprint in effective_sprints:
        w = raw_weights.get(sprint.id, Decimal('0'))
        # Proportion of days_required for this sprint
        proportional = ceil_quarter(days_required * w / total_weight)
        # Cap at phase max_days_per_sprint
        sprint_days[sprint.id] = min(proportional, effective_max)

    # ── Step 4: Normalise to days_required ───────────────────────────────────
    # Simple normalisation: scale proportionally so sum = days_required
    total = sum(sprint_days.values())
    if total > 0 and total != days_required:
        factor = days_required / total
        sprint_days = {
            sid: ceil_quarter(d * factor)
            for sid, d in sprint_days.items()
        }

    # ── Step 5: Apply budget caps ─────────────────────────────────────────────
    # If a sprint is budget-capped, reduce its days and carry remainder forward
    capped_sprints   = set()
    uncapped_sprints = []
    remainder        = Decimal('0')

    for sprint in effective_sprints:
        cap = budget_caps.get(sprint.id)
        if cap is not None and sprint_days.get(sprint.id, 0) > cap:
            remainder += sprint_days[sprint.id] - cap
            sprint_days[sprint.id] = cap
            capped_sprints.add(sprint.id)
        else:
            uncapped_sprints.append(sprint.id)

    # Spread remainder across uncapped sprints
    if remainder > 0 and uncapped_sprints:
        extra_per_sprint = ceil_quarter(remainder / len(uncapped_sprints))
        for sid in uncapped_sprints:
            cap = budget_caps.get(sid)
            additional = min(extra_per_sprint, remainder)
            if cap:
                additional = min(additional, cap - sprint_days[sid])
            sprint_days[sid] = sprint_days.get(sid, Decimal('0')) + additional
            remainder -= additional
            if remainder <= 0:
                break

    return sprint_days


def resolve_engineers(node: PhaseNode,
                       engineer_states: dict,
                       effective_sprints: list,
                       ramp_days: dict,
                       conflicts: list) -> list[dict]:
    """
    Returns list of {engineer_key, split_mode, split_value, assignment_id}
    representing engineers to allocate for this phase.

    Manual assignments are used as-is.
    Auto-assign slots are filled using balanced utilisation logic.
    """

    assignments    = db.get_assignments(node.phase_id)
    manual         = [a for a in assignments if not a.auto_assign]
    auto_slots     = [a for a in assignments if a.auto_assign]
    resolved       = []

    # Manual assignments
    for a in manual:
        key = a.team_member_id
        if key not in engineer_states:
            conflicts.append(make_conflict(
                'CAPACITY_EXCEEDED', 'WARNING',
                node, a.team_member_id,
                f'Assigned engineer {a.team_member_id} not found in capacity tables.'
            ))
            continue
        resolved.append({
            'engineer_key' : key,
            'split_mode'   : node.split_mode,
            'split_value'  : a.split_value,
            'assignment_id': a.id,
            'assignment_type': a.assignment_type,
            'includes_in_budget': a.includes_in_budget,
        })

    # Auto-assign: pick from team members with best utilisation balance
    if auto_slots:
        eligible = [
            state for mid, state in engineer_states.items()
            if state.team_id == node.team_id
            and mid not in {r['engineer_key'] for r in resolved}
        ]

        if not eligible:
            conflicts.append(make_conflict(
                'UNRESOLVABLE_GAP', 'ERROR',
                node, None,
                'No eligible engineers available for auto-assign in this team.'
            ))
        else:
            # Total days needed across the phase
            total_needed    = sum(ramp_days.values())
            max_per_engineer = SPRINT_DURATION_DAYS * len(effective_sprints)

            if node.allow_multiple:
                # Assign to underutilised engineers until days_required met
                # or no more eligible engineers
                remaining_need = total_needed
                team_net       = {
                    e.team_member_id: sum(e.remaining.values())
                    for e in eligible
                }
                team_avg_util  = (
                    sum(1 - (r / max_per_engineer) for r in team_net.values())
                    / len(team_net)
                ) if team_net else Decimal('0')

                # Sort: most underutilised first
                sorted_eligible = sorted(
                    eligible,
                    key=lambda e: (
                        sum(e.allocated.values()) / max(sum(e.remaining.values()), 1)
                    )
                )

                for eng in sorted_eligible:
                    if remaining_need <= 0:
                        break
                    resolved.append({
                        'engineer_key'     : eng.team_member_id,
                        'split_mode'       : 'AUTO',
                        'split_value'      : None,
                        'assignment_id'    : auto_slots[0].id,
                        'assignment_type'  : 'ENGINEER',
                        'includes_in_budget': True,
                    })
                    remaining_need -= sum(eng.remaining.get(s.id, 0)
                                          for s in effective_sprints)
            else:
                # Single engineer: pick most underutilised
                best = min(
                    eligible,
                    key=lambda e: (
                        sum(e.allocated.values()) /
                        max(sum(e.remaining.values()) +
                            sum(e.allocated.values()), Decimal('1'))
                    )
                )
                resolved.append({
                    'engineer_key'     : best.team_member_id,
                    'split_mode'       : 'AUTO',
                    'split_value'      : None,
                    'assignment_id'    : auto_slots[0].id,
                    'assignment_type'  : 'ENGINEER',
                    'includes_in_budget': True,
                })

    return resolved


def write_phase_allocations(node, assigned_engineers, ramp_days,
                              effective_sprints, engineer_states,
                              budget_caps, allocation_set, conflicts):
    """
    Write ResourcePlanAllocation rows for each engineer × sprint in phase.
    Respects:
      - Engineer remaining capacity
      - Phase max_days_per_sprint (combined cap across all engineers)
      - Budget release caps per sprint
      - Split mode and split values
    """

    total_allocated  = Decimal('0')
    programme_id     = db.get_project_programme(node.project_id)

    for sprint in effective_sprints:
        target_days  = ramp_days.get(sprint.id, Decimal('0'))
        budget_cap   = budget_caps.get(sprint.id)
        phase_cap    = node.max_days_per_sprint
        sprint_total = Decimal('0')

        # Compute each engineer's share of target_days for this sprint
        engineer_shares = compute_engineer_shares(
            assigned_engineers, target_days, sprint.id,
            engineer_states, phase_cap
        )

        for eng_info, share in engineer_shares.items():
            state = engineer_states[eng_info]

            # Cap at engineer remaining capacity
            available = state.remaining.get(sprint.id, Decimal('0'))
            days      = min(share, available)
            days      = ceil_quarter(days)

            # Cap at phase max (combined)
            if phase_cap:
                remaining_phase_cap = max(phase_cap - sprint_total, Decimal('0'))
                days = min(days, remaining_phase_cap)

            # Cap at budget release
            if budget_cap:
                remaining_budget_cap = max(budget_cap - sprint_total, Decimal('0'))
                days = min(days, remaining_budget_cap)

            if days <= 0:
                continue

            # Check for capacity exceeded conflict
            if days < share * Decimal('0.5'):
                # Allocated less than half of intended share → conflict
                conflicts.append(make_conflict(
                    'CAPACITY_EXCEEDED', 'ERROR',
                    node, eng_info if isinstance(eng_info, int) else None,
                    f'Engineer capacity insufficient in sprint {sprint.id}. '
                    f'Needed {share:.2f}d, allocated {days:.2f}d.',
                ))

            db.save_allocation(
                allocation_set_id   = allocation_set.id,
                programme_id        = programme_id,
                project_id          = node.project_id,
                team_id             = node.team_id,
                team_member_id      = eng_info if isinstance(eng_info, int) else None,
                placeholder_eng_id  = eng_info if isinstance(eng_info, str) else None,
                sprint_id           = sprint.id,
                phase_id            = node.phase_id,
                assignment_type     = 'ENGINEER',
                includes_in_budget  = True,
                engine_days         = days,
            )

            # Update live state
            state.remaining[sprint.id] -= days
            state.allocated[sprint.id] += days
            sprint_total  += days
            total_allocated += days

    return total_allocated


def compute_engineer_shares(assigned_engineers, target_days, sprint_id,
                              engineer_states, phase_cap):
    """
    Return {engineer_key → share_days} for this sprint.

    Respects split_mode: PERCENT / DAYS / EQUAL / AUTO.
    """
    shares = {}
    n      = len(assigned_engineers)
    if n == 0:
        return shares

    for eng in assigned_engineers:
        key        = eng['engineer_key']
        split_mode = eng['split_mode']
        split_val  = eng['split_value']

        if split_mode == 'PERCENT' and split_val:
            shares[key] = ceil_quarter(target_days * split_val / 100)

        elif split_mode == 'DAYS' and split_val:
            # Fixed days per sprint (not as a share of target)
            shares[key] = min(split_val, target_days)

        elif split_mode == 'EQUAL':
            shares[key] = ceil_quarter(target_days / n)

        else:  # AUTO
            # Proportional to remaining capacity in this sprint
            total_remaining = sum(
                engineer_states[e['engineer_key']].remaining.get(sprint_id, 0)
                for e in assigned_engineers
                if e['engineer_key'] in engineer_states
            )
            if total_remaining > 0:
                eng_remaining = engineer_states[key].remaining.get(
                    sprint_id, Decimal('0')
                )
                shares[key] = ceil_quarter(
                    target_days * eng_remaining / total_remaining
                )
            else:
                shares[key] = ceil_quarter(target_days / n)

    return shares


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — REBALANCE
# ══════════════════════════════════════════════════════════════════════════════

def rebalance_utilisation(engineer_states, allocation_set, active_sprints,
                           ordered_phases, job, conflicts):
    """
    Post-allocation rebalancing pass.

    Goal: ensure all engineers have sufficient work.
    When an engineer has remaining bandwidth (below REBALANCE_THRESHOLD_PCT),
    look at other engineers carrying low-priority work and move it to
    the bandwidth-rich engineer.

    Two outcomes:
      1. Low-priority engineer freed → ramp-down candidate surfaced
      2. Bandwidth-rich engineer filled → better FY utilisation
    """

    PRIORITY_RANK = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    net_capacity_map = {
        mid: {s.id: SPRINT_DURATION_DAYS for s in active_sprints}
        for mid in engineer_states
    }

    def eng_utilisation(state):
        total_net  = sum(state.remaining.get(s.id, 0) +
                         state.allocated.get(s.id, 0)
                         for s in active_sprints)
        total_alloc = sum(state.allocated.values())
        return utilisation_pct(total_alloc, total_net)

    underutilised = [
        state for state in engineer_states.values()
        if eng_utilisation(state) < REBALANCE_THRESHOLD_PCT
    ]

    for state in underutilised:
        # Find low-priority allocations on other engineers
        # that could be moved here
        candidate_allocations = db.get_low_priority_allocations(
            allocation_set_id = allocation_set.id,
            exclude_member_id = state.team_member_id,
            team_id           = state.team_id,
        )

        # Sort by lowest priority first (most moveable)
        candidate_allocations.sort(
            key=lambda a: PRIORITY_RANK.get(
                db.get_project_priority(a.project_id), 99
            ),
            reverse=True  # lowest priority first
        )

        for alloc in candidate_allocations:
            if eng_utilisation(state) >= REBALANCE_THRESHOLD_PCT:
                break

            available = state.remaining.get(alloc.sprint_id, Decimal('0'))
            if available <= 0:
                continue

            # Can we move some or all of this allocation to our engineer?
            days_to_move = min(alloc.engine_days, available)
            days_to_move = ceil_quarter(days_to_move)

            if days_to_move <= 0:
                continue

            # Move the allocation
            db.reduce_allocation(alloc.id, days_to_move)
            db.save_allocation(
                allocation_set_id  = allocation_set.id,
                programme_id       = alloc.programme_id,
                project_id         = alloc.project_id,
                team_id            = state.team_id,
                team_member_id     = state.team_member_id,
                sprint_id          = alloc.sprint_id,
                phase_id           = alloc.phase_id,
                assignment_type    = alloc.assignment_type,
                includes_in_budget = alloc.includes_in_budget,
                engine_days        = days_to_move,
            )

            # Update live state
            state.remaining[alloc.sprint_id] -= days_to_move
            state.allocated[alloc.sprint_id] = (
                state.allocated.get(alloc.sprint_id, Decimal('0')) + days_to_move
            )

            # Record rebalance in audit
            db.write_audit_log(
                plan_id     = allocation_set.plan_id,
                event_type  = 'ALLOCATION_OVERRIDE',
                entity_type = 'ResourcePlanAllocation',
                entity_id   = alloc.id,
                before_state= {'engine_days': float(alloc.engine_days)},
                after_state = {
                    'engine_days': float(alloc.engine_days - days_to_move),
                    'moved_to'   : state.team_member_id,
                    'reason'     : 'rebalance',
                },
            )


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — CONFLICT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_threshold_conflicts(plan, allocation_set, ordered_phases, conflicts):
    """
    For each plan project, compare total allocated ENGINEER days
    against days_required using threshold_pct from ResourcePlanVersion.
    Raise THRESHOLD_BREACH conflict if outside band.
    """

    version       = db.get_plan_version(plan.id)
    threshold_pct = version.threshold_pct / 100

    plan_projects = db.get_plan_projects(plan.id)

    for pp in plan_projects:
        allocated = db.sum_budget_allocations(
            allocation_set_id = allocation_set.id,
            project_id        = pp.project_id,
        )

        lower = pp.days_required * (1 - threshold_pct)
        upper = pp.days_required * (1 + threshold_pct)

        if allocated > upper:
            db.set_threshold_flags(pp.id, over=True, under=False)
            conflicts.append({
                'conflict_type'   : 'THRESHOLD_BREACH',
                'severity'        : 'WARNING',
                'affected_project': pp.project_id,
                'description'     : (
                    f'Project allocated {allocated:.2f}d exceeds '
                    f'days_required {pp.days_required:.2f}d by more than '
                    f'{version.threshold_pct}%.'
                ),
                'engine_data'     : {
                    'allocated'    : float(allocated),
                    'days_required': float(pp.days_required),
                    'threshold_pct': float(version.threshold_pct),
                },
            })

        elif allocated < lower:
            db.set_threshold_flags(pp.id, over=False, under=True)
            conflicts.append({
                'conflict_type'   : 'THRESHOLD_BREACH',
                'severity'        : 'WARNING',
                'affected_project': pp.project_id,
                'description'     : (
                    f'Project allocated {allocated:.2f}d is below '
                    f'days_required {pp.days_required:.2f}d by more than '
                    f'{version.threshold_pct}%.'
                ),
                'engine_data'     : {
                    'allocated'    : float(allocated),
                    'days_required': float(pp.days_required),
                    'threshold_pct': float(version.threshold_pct),
                },
            })
        else:
            db.set_threshold_flags(pp.id, over=False, under=False)


def detect_rampdown_candidates(engineer_states, active_sprints,
                                 allocation_set, conflicts):
    """
    After rebalancing, flag engineers whose FY utilisation is
    below RAMPDOWN_THRESHOLD_PCT as ramp-down candidates.
    INFO severity — informational only.
    """

    for mid, state in engineer_states.items():
        total_capacity = SPRINT_DURATION_DAYS * len(active_sprints)
        total_alloc    = sum(state.allocated.values())
        util           = utilisation_pct(total_alloc, total_capacity)

        if util < RAMPDOWN_THRESHOLD_PCT:
            conflicts.append({
                'conflict_type'      : 'CAPACITY_EXCEEDED',
                'severity'           : 'INFO',
                'affected_team_member':
                    mid if isinstance(mid, int) else None,
                'description'        : (
                    f'Engineer utilisation is {util:.1f}% for the FY — '
                    f'below ramp-down threshold of {RAMPDOWN_THRESHOLD_PCT}%. '
                    f'Consider rebalancing workload or initiating ramp-down.'
                ),
                'engine_data'        : {
                    'utilisation_pct'    : float(util),
                    'rampdown_threshold' : float(RAMPDOWN_THRESHOLD_PCT),
                    'total_allocated_days': float(total_alloc),
                },
            })


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 8 — UTILISATION SUMMARIES
# ══════════════════════════════════════════════════════════════════════════════

def compute_utilisation_summaries(engineer_states, allocation_set,
                                   active_sprints, job):
    """
    Compute and store ResourcePlanTeamUtilisation and
    ResourcePlanMemberUtilisation for every engineer × sprint.
    Called immediately after allocation — no separate trigger required.
    Programme-level rollup is handled by the service layer on demand.
    """

    db.delete_utilisation_summaries(allocation_set.id)

    # ── Member utilisation ────────────────────────────────────────────────────
    for mid, state in engineer_states.items():
        for sprint in active_sprints:
            total_cap    = SPRINT_DURATION_DAYS
            absence_days = db.get_absence_days(
                allocation_set.plan_id, mid, sprint.id
            )
            placeholder  = db.get_placeholder_leave_days(
                allocation_set.plan_id, mid, sprint.id
            )
            net_cap      = max(total_cap - absence_days - placeholder,
                               Decimal('0'))
            allocated    = state.allocated.get(sprint.id, Decimal('0'))
            budget_alloc = db.get_budget_allocated_days(
                allocation_set.id, mid, sprint.id
            )
            non_budget   = allocated - budget_alloc
            util_pct     = utilisation_pct(allocated, net_cap)

            breakdown = db.get_project_breakdown_for_member(
                allocation_set.id, mid, sprint.id
            )

            is_placeholder_eng = isinstance(mid, str) and mid.startswith('pe_')
            pe_id = int(mid[3:]) if is_placeholder_eng else None
            tm_id = mid if not is_placeholder_eng else None

            db.save_member_utilisation(
                allocation_set_id    = allocation_set.id,
                team_member_id       = tm_id,
                placeholder_eng_id   = pe_id,
                sprint_id            = sprint.id,
                total_capacity_days  = total_cap,
                absence_days         = absence_days,
                placeholder_days     = placeholder,
                net_capacity_days    = net_cap,
                allocated_days       = allocated,
                budget_allocated_days= budget_alloc,
                non_budget_days      = non_budget,
                project_breakdown    = breakdown,
                utilisation_pct      = util_pct,
                is_over_utilised     = util_pct > 100,
                is_under_utilised    = util_pct < RAMPDOWN_THRESHOLD_PCT,
                job_id               = job.id,
            )

    # ── Team utilisation ──────────────────────────────────────────────────────
    teams = db.get_all_plan_teams(allocation_set.plan_id)

    for team in teams:
        team_members = [
            state for mid, state in engineer_states.items()
            if state.team_id == team.id
        ]

        for sprint in active_sprints:
            total_cap   = sum(
                SPRINT_DURATION_DAYS for _ in team_members
            )
            absence     = sum(
                db.get_absence_days(
                    allocation_set.plan_id, m.team_member_id, sprint.id
                ) for m in team_members
            )
            placeholder = sum(
                db.get_placeholder_leave_days(
                    allocation_set.plan_id, m.team_member_id, sprint.id
                ) for m in team_members
            )
            net_cap     = max(total_cap - absence - placeholder, Decimal('0'))
            allocated   = sum(
                m.allocated.get(sprint.id, Decimal('0'))
                for m in team_members
            )
            budget_alloc= db.get_team_budget_allocated(
                allocation_set.id, team.id, sprint.id
            )
            non_budget  = allocated - budget_alloc
            util_pct    = utilisation_pct(allocated, net_cap)

            db.save_team_utilisation(
                allocation_set_id     = allocation_set.id,
                team_id               = team.id,
                sprint_id             = sprint.id,
                total_capacity_days   = total_cap,
                absence_days          = absence,
                placeholder_days      = placeholder,
                net_capacity_days     = net_cap,
                allocated_days        = allocated,
                budget_allocated_days = budget_alloc,
                non_budget_days       = non_budget,
                utilisation_pct       = util_pct,
                is_over_utilised      = util_pct > 100,
                job_id                = job.id,
            )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def resolve_active_sprints(all_sprints, today_sprint, include_current):
    """
    Return sprints the engine may write to.
    - Excludes all past sprints
    - Includes current sprint only if include_current=True
    """
    if not today_sprint:
        return all_sprints

    result = []
    found_current = False

    for sprint in all_sprints:
        if sprint.id == today_sprint.id:
            found_current = True
            if include_current:
                result.append(sprint)
        elif found_current:
            result.append(sprint)

    return result


def make_conflict(conflict_type, severity, node, member_id, description,
                   engine_data=None) -> dict:
    return {
        'conflict_type'      : conflict_type,
        'severity'           : severity,
        'affected_project'   : node.project_id,
        'affected_phase'     : node.phase_id,
        'affected_team_member': member_id,
        'affected_team'      : node.team_id,
        'description'        : description,
        'engine_data'        : engine_data or {},
    }
