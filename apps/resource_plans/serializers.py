from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

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
    ResourcePlanPlaceholderEngineer,
    ResourcePlanAllocationSet,
    ResourcePlanAllocation,
    Conflict,
    ManpowerRequest,
)


class ResourcePlanVersionSerializer(serializers.ModelSerializer):
    cloned_from_plan_name = serializers.SerializerMethodField()
    plan_id = serializers.IntegerField(source="plan.id", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_created_at = serializers.DateTimeField(source="plan.created_at", read_only=True)
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlanVersion
        fields = [
            "id",
            "plan_id",
            "plan_name",
            "plan_created_at",
            "plan_group",
            "version",
            "status",
            "threshold_pct",
            "has_pl_overrides",
            "has_allocation_overrides",
            "cloned_from",
            "cloned_from_plan_name",
            "project_count",
        ]

    def get_cloned_from_plan_name(self, obj):
        if obj.cloned_from:
            return obj.cloned_from.plan.name
        return None

    def get_project_count(self, obj):
        return obj.projects.count()


class ResourcePlanScopeSerializer(serializers.ModelSerializer):
    financial_year_short = serializers.SerializerMethodField()
    financial_year_long = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    programme_name = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlanScope
        fields = [
            "plan_group",
            "financial_year",
            "financial_year_short",
            "financial_year_long",
            "project",
            "project_name",
            "programme",
            "programme_name",
            "team",
            "team_name",
        ]

    def get_financial_year_short(self, obj):
        return obj.financial_year.short_fy if obj.financial_year else None
    
    def get_financial_year_long(self, obj):
        return obj.financial_year.long_fy if obj.financial_year else None

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

    def get_programme_name(self, obj):
        return obj.programme.name if obj.programme else None

    def get_team_name(self, obj):
        return obj.team.name if obj.team else None


class ResourcePlanListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view."""

    financial_year_short = serializers.SerializerMethodField()
    financial_year_long = serializers.SerializerMethodField()
    version_number = serializers.SerializerMethodField()
    plan_group = serializers.SerializerMethodField()
    threshold_pct = serializers.SerializerMethodField()
    cloned_from_name = serializers.SerializerMethodField()
    scope = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlan
        fields = [
            "id",
            "name",
            "description",
            "plan_type",
            "financial_year",
            "financial_year_short",
            "financial_year_long",
            "version_number",
            "plan_group",
            "threshold_pct",
            "cloned_from",
            "cloned_from_name",
            "scope",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_financial_year_short(self, obj):
        return obj.financial_year.short_fy if obj.financial_year else None
    
    def get_financial_year_long(self, obj):
        return obj.financial_year.long_fy if obj.financial_year else None

    def get_version_number(self, obj):
        try:
            return obj.version.version
        except Exception:
            return None

    def get_plan_group(self, obj):
        try:
            return str(obj.version.plan_group)
        except Exception:
            return None

    def get_threshold_pct(self, obj):
        try:
            return str(obj.version.threshold_pct)
        except Exception:
            return None

    def get_cloned_from_name(self, obj):
        return obj.cloned_from.name if obj.cloned_from else None

    def get_status(self, obj):
        try:
            return obj.version.status
        except Exception:
            return None

    def get_scope(self, obj):
        try:
            scope = ResourcePlanScope.objects.select_related(
                "financial_year", "project", "programme", "team"
            ).get(plan_group=obj.version.plan_group)
            return ResourcePlanScopeSerializer(scope).data
        except ResourcePlanScope.DoesNotExist:
            return None


class ResourcePlanSerializer(serializers.ModelSerializer):
    """Full detail serializer."""

    version_info = ResourcePlanVersionSerializer(source="version", read_only=True)
    scope = serializers.SerializerMethodField()
    cloned_from_name = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlan
        fields = [
            "id",
            "name",
            "description",
            "plan_type",
            "financial_year",
            "cloned_from",
            "cloned_from_name",
            "version_info",
            "scope",
            "status",
            "is_active",
            "comment_count",
            "created_at",
            "updated_at",
        ]

    def get_status(self, obj):
        try:
            return obj.version.status
        except Exception:
            return None

    def get_scope(self, obj):
        try:
            scope = ResourcePlanScope.objects.select_related(
                "financial_year", "project", "programme", "team"
            ).get(plan_group=obj.version.plan_group)
            return ResourcePlanScopeSerializer(scope).data
        except ResourcePlanScope.DoesNotExist:
            return None

    def get_cloned_from_name(self, obj):
        return obj.cloned_from.name if obj.cloned_from else None

    def get_comment_count(self, obj):
        return obj.comments.count()


class ResourcePlanCreateSerializer(serializers.Serializer):
    """Atomic creation of Plan + Version + Scope."""

    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    plan_type = serializers.ChoiceField(choices=ResourcePlan.PLAN_TYPE_CHOICES)
    financial_year = serializers.IntegerField()
    project = serializers.IntegerField(required=False, allow_null=True, default=None)
    programme = serializers.IntegerField(required=False, allow_null=True, default=None)
    team = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate(self, data):
        plan_type = data.get("plan_type")
        if plan_type == ResourcePlan.PLAN_TYPE_PROJECT and not data.get("project"):
            raise serializers.ValidationError(
                {"project": "Project is required for PROJECT plan type."}
            )
        if plan_type == ResourcePlan.PLAN_TYPE_PROGRAMME and not data.get("programme"):
            raise serializers.ValidationError(
                {"programme": "Programme is required for PROGRAMME plan type."}
            )
        if plan_type == ResourcePlan.PLAN_TYPE_TEAM and not data.get("team"):
            raise serializers.ValidationError(
                {"team": "Team is required for TEAM plan type."}
            )
        return data


class ResourcePlanCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourcePlanComment
        fields = ["id", "comment", "posted_by", "created_at"]
        read_only_fields = ["id", "created_at"]


class ResourcePlanVersionProjectSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    programme_name = serializers.SerializerMethodField()
    programme_id = serializers.SerializerMethodField()
    effective_priority = serializers.CharField(read_only=True)
    effective_confidence = serializers.CharField(read_only=True)
    start_sprint_name = serializers.SerializerMethodField()
    end_sprint_name = serializers.SerializerMethodField()
    team_count = serializers.SerializerMethodField()
    release_count = serializers.SerializerMethodField()
    release_sum = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlanVersionProject
        fields = [
            "id", "project", "project_name", "programme_name", "programme_id",
            "basis", "basis_amount", "basis_synced_at",
            "snapshotted_estimate",
            "days_required",
            "is_over_threshold", "is_under_threshold",
            "is_team_budget_mismatch", "is_percent_incomplete",
            "priority_snapshot", "priority_override", "effective_priority",
            "confidence_snapshot", "confidence_override", "effective_confidence",
            "start_sprint", "start_sprint_name", "end_sprint", "end_sprint_name",
            "dates_strict", "budget_release_mode",
            "display_order", "created_at", "updated_at",
            "team_count", "release_count", "release_sum",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_programme_name(self, obj):
        return obj.project.programme.name if obj.project.programme else None

    def get_programme_id(self, obj):
        return obj.project.programme_id

    def get_start_sprint_name(self, obj):
        return obj.start_sprint.sprint_name if obj.start_sprint else None

    def get_end_sprint_name(self, obj):
        return obj.end_sprint.sprint_name if obj.end_sprint else None

    def get_team_count(self, obj):
        return obj.teams.count()

    def get_release_count(self, obj):
        return obj.budget_releases.count()

    def get_release_sum(self, obj):
        from decimal import Decimal
        releases = obj.budget_releases.all()
        if not releases:
            return None
        total = sum(r.amount for r in releases)
        return str(total)


class ResourcePlanVersionProjectTeamSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = ResourcePlanVersionProjectTeam
        fields = [
            "id", "team", "team_name",
            "allocation_type", "allocation_pct", "allocation_days", "allocation_budget",
            "allocated_days", "sequence_order",
        ]
        read_only_fields = ["id", "allocated_days"]


class ResourcePlanVersionProjectBudgetReleaseSerializer(serializers.ModelSerializer):
    sprint_name = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlanVersionProjectBudgetRelease
        fields = ["id", "entry_type", "sprint", "sprint_name", "month", "amount", "notes"]
        read_only_fields = ["id"]

    def get_sprint_name(self, obj):
        return obj.sprint.sprint_name if obj.sprint else None


class PlanPhaseSerializer(serializers.ModelSerializer):
    start_sprint_name = serializers.SerializerMethodField()
    end_sprint_name = serializers.SerializerMethodField()
    segment_count = serializers.SerializerMethodField()
    dependency_count = serializers.SerializerMethodField()
    pause_count = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()

    class Meta:
        model = PlanPhase
        fields = [
            "id", "plan_project_team", "name", "sequence_order",
            "start_sprint", "start_sprint_name", "end_sprint", "end_sprint_name",
            "max_days_per_sprint", "ramp_pattern",
            "allow_multiple_engineers", "split_mode", "is_split_incomplete",
            "notes", "days_effort", "segment_count", "dependency_count", "pause_count", "assignment_count",
        ]
        read_only_fields = ["id"]

    def get_start_sprint_name(self, obj):
        return obj.start_sprint.sprint_name if obj.start_sprint else None

    def get_end_sprint_name(self, obj):
        return obj.end_sprint.sprint_name if obj.end_sprint else None

    def get_segment_count(self, obj):
        return obj.segments.count()

    def get_dependency_count(self, obj):
        return obj.dependencies.count()

    def get_pause_count(self, obj):
        return obj.pauses.count()

    def get_assignment_count(self, obj):
        return obj.assignments.count()


class PlanPhaseSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPhaseSegment
        fields = [
            "id", "phase", "segment_order", "segment_type",
            "start_pct", "end_pct", "progression", "duration", "step_count",
        ]
        read_only_fields = ["id"]


class PlanPhaseDependencySerializer(serializers.ModelSerializer):
    predecessor_phase_name = serializers.CharField(source="predecessor_phase.name", read_only=True)
    predecessor_project_name = serializers.SerializerMethodField()

    class Meta:
        model = PlanPhaseDependency
        fields = [
            "id", "phase", "predecessor_phase", "predecessor_phase_name",
            "predecessor_project_name", "dependency_type", "lag_sprints",
        ]
        read_only_fields = ["id"]

    def get_predecessor_project_name(self, obj):
        team = obj.predecessor_phase.plan_project_team
        return team.plan_project.project.name if team else None


class PlanPhasePauseSerializer(serializers.ModelSerializer):
    pause_from_name = serializers.SerializerMethodField()
    pause_until_sprint_name = serializers.SerializerMethodField()
    resume_sprint_name = serializers.SerializerMethodField()

    class Meta:
        model = PlanPhasePause
        fields = [
            "id", "phase", "pause_from", "pause_from_name",
            "input_mode", "pause_until_sprint", "pause_until_sprint_name",
            "pause_sprint_count", "resume_sprint", "resume_sprint_name",
            "is_beyond_fy", "notes",
        ]
        read_only_fields = ["id", "resume_sprint", "is_beyond_fy"]

    def get_pause_from_name(self, obj):
        return obj.pause_from.sprint_name if obj.pause_from else None

    def get_pause_until_sprint_name(self, obj):
        return obj.pause_until_sprint.sprint_name if obj.pause_until_sprint else None

    def get_resume_sprint_name(self, obj):
        return obj.resume_sprint.sprint_name if obj.resume_sprint else None


class PlanAssignmentSerializer(serializers.ModelSerializer):
    team_member_name = serializers.SerializerMethodField()
    replaces_member_name = serializers.SerializerMethodField()

    class Meta:
        model = PlanAssignment
        fields = [
            "id", "phase",
            "team_member", "team_member_name",
            "auto_assign", "assignment_type",
            "replaces_member", "replaces_member_name",
            "interim_sprint_count", "split_value",
            "includes_in_budget", "notes",
        ]
        read_only_fields = ["id", "includes_in_budget"]

    def get_team_member_name(self, obj):
        return obj.team_member.display_name if obj.team_member else None

    def get_replaces_member_name(self, obj):
        return obj.replaces_member.display_name if obj.replaces_member else None


class PlanEngineJobSerializer(serializers.ModelSerializer):
    version_number = serializers.SerializerMethodField()

    class Meta:
        model = PlanEngineJob
        fields = [
            "id", "plan", "version", "version_number", "status", "mode",
            "current_step", "progress_pct",
            "include_current_sprint", "dry_run", "remove_overrides",
            "initiated_at", "started_at", "completed_at", "duration_seconds",
            "validation_result", "steps_log", "error_log",
        ]
        read_only_fields = fields

    def get_version_number(self, obj):
        return obj.version.version if obj.version else None


class PlanEngineJobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanEngineJob
        fields = ["id", "status", "mode", "current_step", "progress_pct", "duration_seconds"]
        read_only_fields = fields


class PlaceholderLeaveSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="team_member.display_name", read_only=True)
    team_id = serializers.IntegerField(source="team_member.team_id", read_only=True)
    sprint_name = serializers.CharField(source="sprint.sprint_name", read_only=True)

    class Meta:
        model = PlaceholderLeave
        fields = [
            "id", "version", "team_member", "member_name", "team_id",
            "sprint", "sprint_name", "days", "is_auto", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "version", "team_member", "sprint", "is_auto", "created_at", "updated_at"]


class ResourcePlanPlaceholderEngineerSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    phase_name = serializers.CharField(source="phase.name", read_only=True)

    class Meta:
        model = ResourcePlanPlaceholderEngineer
        fields = [
            "id", "version", "team", "team_name", "phase", "phase_name",
            "slot_number", "name", "assignment_type",
        ]
        read_only_fields = fields


class ResourcePlanAllocationSetSerializer(serializers.ModelSerializer):
    allocation_count = serializers.SerializerMethodField()
    conflict_count = serializers.SerializerMethodField()
    open_error_count = serializers.SerializerMethodField()

    class Meta:
        model = ResourcePlanAllocationSet
        fields = [
            "id", "version", "engine_job", "status",
            "activated_at", "notes",
            "created_at", "updated_at",
            "allocation_count", "conflict_count", "open_error_count",
        ]
        read_only_fields = [
            "id", "version", "engine_job", "status",
            "activated_at", "created_at", "updated_at",
            "allocation_count", "conflict_count", "open_error_count",
        ]

    def get_allocation_count(self, obj):
        return obj.allocations.count()

    def get_conflict_count(self, obj):
        return obj.conflicts.count()

    def get_open_error_count(self, obj):
        return obj.conflicts.filter(severity=Conflict.SEVERITY_ERROR, status=Conflict.STATUS_OPEN).count()


class ResourcePlanAllocationSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    sprint_number = serializers.IntegerField(source="sprint.sprint_number", read_only=True)
    effective_days = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )

    class Meta:
        model = ResourcePlanAllocation
        fields = [
            "id", "allocation_set", "programme", "project", "project_name",
            "team", "team_name", "team_member", "member_name",
            "placeholder_engineer", "sprint", "sprint_number",
            "phase", "assignment", "assignment_type", "includes_in_budget",
            "engine_days", "override_days", "override_notes", "overridden_at",
            "effective_days",
        ]
        read_only_fields = [
            "id", "allocation_set", "programme", "project", "team",
            "team_member", "placeholder_engineer", "sprint", "phase",
            "assignment", "assignment_type", "includes_in_budget",
            "engine_days", "overridden_at", "effective_days",
            "project_name", "team_name", "member_name", "sprint_number",
        ]

    def get_member_name(self, obj):
        if obj.team_member:
            return obj.team_member.display_name
        if obj.placeholder_engineer:
            return obj.placeholder_engineer.name
        return None


class ConflictSerializer(serializers.ModelSerializer):
    affected_project_name = serializers.SerializerMethodField()
    affected_phase_name = serializers.SerializerMethodField()
    affected_member_name = serializers.SerializerMethodField()
    affected_sprint_name = serializers.SerializerMethodField()
    affected_team_name = serializers.SerializerMethodField()
    allowed_resolutions = serializers.SerializerMethodField()

    class Meta:
        model = Conflict
        fields = [
            'id', 'allocation_set', 'engine_job', 'conflict_type', 'severity',
            'status', 'affected_project', 'affected_project_name', 'affected_phase',
            'affected_phase_name', 'affected_team_member', 'affected_member_name',
            'affected_sprint', 'affected_sprint_name', 'affected_team', 'affected_team_name',
            'description', 'engine_data', 'resolution_type', 'resolution_notes',
            'resolved_at', 'created_at', 'allowed_resolutions',
        ]

    def get_affected_project_name(self, obj):
        return obj.affected_project.name if obj.affected_project else None

    def get_affected_phase_name(self, obj):
        return obj.affected_phase.name if obj.affected_phase else None

    def get_affected_member_name(self, obj):
        return obj.affected_team_member.display_name if obj.affected_team_member else None

    def get_affected_sprint_name(self, obj):
        return obj.affected_sprint.sprint_name if obj.affected_sprint else None

    def get_affected_team_name(self, obj):
        return obj.affected_team.name if obj.affected_team else None

    def get_allowed_resolutions(self, obj):
        from .services import ConflictResolutionService
        return ConflictResolutionService.ALLOWED_RESOLUTIONS.get(obj.conflict_type, [Conflict.RES_DISMISSED])


class ManpowerRequestSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    phase_name = serializers.SerializerMethodField()
    conflict_type = serializers.CharField(source='conflict.conflict_type', read_only=True)

    class Meta:
        model = ManpowerRequest
        fields = [
            'id', 'allocation_set', 'conflict', 'conflict_type', 'team', 'team_name',
            'phase', 'phase_name', 'sprints_needed', 'days_needed',
            'status', 'resolution_notes', 'resolved_at', 'created_at',
        ]

    def get_phase_name(self, obj):
        return obj.phase.name if obj.phase else None
