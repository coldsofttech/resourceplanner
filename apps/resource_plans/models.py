from django.conf import settings
from django.db import models


class ResourcePlan(models.Model):
    PLAN_TYPE_FY = "FY"
    PLAN_TYPE_PROJECT = "PROJECT"
    PLAN_TYPE_PROGRAMME = "PROGRAMME"
    PLAN_TYPE_TEAM = "TEAM"
    PLAN_TYPE_CHOICES = [
        (PLAN_TYPE_FY, "Financial Year"),
        (PLAN_TYPE_PROJECT, "Project"),
        (PLAN_TYPE_PROGRAMME, "Programme"),
        (PLAN_TYPE_TEAM, "Team"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES)
    cloned_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clones",
    )
    financial_year = models.ForeignKey(
        "financial_years.FinancialYear",
        on_delete=models.PROTECT,
        related_name="resource_plan",
    )
    is_active = models.BooleanField(default=True)
    is_head = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ResourcePlanVersion(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_LOCKED = "LOCKED"
    STATUS_SUPERSEDED = "SUPERSEDED"
    STATUS_EXPIRED = "EXPIRED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_LOCKED, "Locked"),
        (STATUS_SUPERSEDED, "Superseded"),
        (STATUS_EXPIRED, "Expired"),
    ]

    plan = models.OneToOneField(
        ResourcePlan, on_delete=models.CASCADE, related_name="version"
    )
    plan_group = models.UUIDField(db_index=True)
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    cloned_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restored_versions",
    )
    threshold_pct = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    has_pl_overrides = models.BooleanField(default=False)
    has_allocation_overrides = models.BooleanField(default=False)

    class Meta:
        unique_together = [("plan_group", "version")]
        ordering = ["-version"]

    def __str__(self):
        return f"{self.plan.name} v{self.version} [{self.status}]"


class ResourcePlanScope(models.Model):
    plan_group = models.UUIDField(unique=True, db_index=True)
    financial_year = models.ForeignKey(
        "financial_years.FinancialYear",
        on_delete=models.PROTECT,
        related_name="resource_plan_scopes",
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resource_plan_scopes",
    )
    programme = models.ForeignKey(
        "programmes.Programme",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resource_plan_scopes",
    )
    team = models.ForeignKey(
        "delivery_teams.DeliveryTeam",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resource_plan_scopes",
    )

    class Meta:
        ordering = ["plan_group"]

    def __str__(self):
        return f"Scope [{self.plan_group}]"


class ResourcePlanVersionProject(models.Model):
    BASIS_BUDGET = "BUDGET"
    BASIS_ESTIMATE = "ESTIMATE"
    BASIS_CUSTOM = "CUSTOM"
    BASIS_CHOICES = [
        (BASIS_BUDGET, "Budget"),
        (BASIS_ESTIMATE, "Estimate"),
        (BASIS_CUSTOM, "Custom"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
    ]

    CONFIDENCE_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
    ]

    BUDGET_RELEASE_SPRINT = "SPRINT"
    BUDGET_RELEASE_MONTH = "MONTH"
    BUDGET_RELEASE_CHOICES = [
        (BUDGET_RELEASE_SPRINT, "Sprint"),
        (BUDGET_RELEASE_MONTH, "Month"),
    ]

    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name="projects"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="resource_plan_version_projects"
    )
    basis = models.CharField(max_length=20, choices=BASIS_CHOICES)
    basis_amount = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    basis_synced_at = models.DateTimeField(null=True, blank=True)
    snapshotted_budget = models.ForeignKey(
        "projects.ProjectBudget", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    snapshotted_estimate = models.ForeignKey(
        "projects.ProjectEstimate", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    days_required = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_over_threshold = models.BooleanField(default=False)
    is_under_threshold = models.BooleanField(default=False)
    is_team_budget_mismatch = models.BooleanField(default=False)
    is_percent_incomplete = models.BooleanField(default=False)
    priority_snapshot = models.CharField(max_length=20, null=True, blank=True)
    priority_override = models.CharField(max_length=20, null=True, blank=True)
    confidence_snapshot = models.CharField(max_length=20, null=True, blank=True)
    confidence_override = models.CharField(max_length=20, null=True, blank=True)
    start_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    end_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    dates_strict = models.BooleanField(default=False)
    budget_release_mode = models.CharField(
        max_length=10, choices=BUDGET_RELEASE_CHOICES, null=True, blank=True
    )
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("version", "project")]
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return f"{self.project.name} in {self.version}"

    @property
    def effective_priority(self):
        return self.priority_override or self.priority_snapshot

    @property
    def effective_confidence(self):
        return self.confidence_override or self.confidence_snapshot


class ResourcePlanVersionProjectTeam(models.Model):
    ALLOC_PERCENT = "PERCENT"
    ALLOC_DAYS = "DAYS"
    ALLOC_BUDGET = "BUDGET"
    ALLOC_CHOICES = [
        (ALLOC_PERCENT, "Percent"),
        (ALLOC_DAYS, "Days"),
        (ALLOC_BUDGET, "Budget"),
    ]

    plan_project = models.ForeignKey(
        ResourcePlanVersionProject, on_delete=models.CASCADE, related_name="teams"
    )
    team = models.ForeignKey(
        "delivery_teams.DeliveryTeam", on_delete=models.PROTECT, related_name="+"
    )
    allocation_type = models.CharField(max_length=20, choices=ALLOC_CHOICES)
    allocation_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    allocation_days = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    allocation_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    allocated_days = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("plan_project", "team")]
        ordering = ["sequence_order", "team__name"]

    def __str__(self):
        return f"{self.team.name} on {self.plan_project}"


class ResourcePlanVersionProjectBudgetRelease(models.Model):
    ENTRY_SPRINT = "SPRINT"
    ENTRY_MONTH = "MONTH"
    ENTRY_CHOICES = [
        (ENTRY_SPRINT, "Sprint"),
        (ENTRY_MONTH, "Month"),
    ]

    plan_project = models.ForeignKey(
        ResourcePlanVersionProject, on_delete=models.CASCADE, related_name="budget_releases"
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_CHOICES)
    sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    month = models.CharField(max_length=3, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["entry_type", "sprint__sprint_number", "month"]

    def __str__(self):
        ref = self.sprint.sprint_name if self.sprint else self.month
        return f"Release {ref}: £{self.amount}"


class PlanPhase(models.Model):
    RAMP_FLAT = "FLAT"
    RAMP_UP = "RAMP_UP"
    RAMP_DOWN = "RAMP_DOWN"
    RAMP_UP_DOWN = "RAMP_UP_DOWN"
    RAMP_UP_STEADY = "RAMP_UP_STEADY"
    STEADY_DOWN = "STEADY_DOWN"
    STEPPED = "STEPPED"
    RAMP_CUSTOM = "CUSTOM"
    RAMP_CHOICES = [
        (RAMP_FLAT, "Flat"),
        (RAMP_UP, "Ramp Up"),
        (RAMP_DOWN, "Ramp Down"),
        (RAMP_UP_DOWN, "Ramp Up/Down"),
        (RAMP_UP_STEADY, "Ramp Up then Steady"),
        (STEADY_DOWN, "Steady then Down"),
        (STEPPED, "Stepped"),
        (RAMP_CUSTOM, "Custom"),
    ]

    SPLIT_PERCENT = "PERCENT"
    SPLIT_DAYS = "DAYS"
    SPLIT_EQUAL = "EQUAL"
    SPLIT_AUTO = "AUTO"
    SPLIT_CHOICES = [
        (SPLIT_PERCENT, "Percent"),
        (SPLIT_DAYS, "Days"),
        (SPLIT_EQUAL, "Equal"),
        (SPLIT_AUTO, "Auto"),
    ]

    plan_project_team = models.ForeignKey(
        ResourcePlanVersionProjectTeam, on_delete=models.CASCADE, related_name="phases"
    )
    name = models.CharField(max_length=100)
    sequence_order = models.PositiveIntegerField(default=1)
    start_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    end_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    max_days_per_sprint = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ramp_pattern = models.CharField(max_length=20, choices=RAMP_CHOICES, default=RAMP_FLAT)
    allow_multiple_engineers = models.BooleanField(default=False)
    split_mode = models.CharField(max_length=10, choices=SPLIT_CHOICES, default=SPLIT_AUTO)
    is_split_incomplete = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    days_effort = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Override: total days this phase should consume (overrides team total ÷ n_phases)."
    )

    class Meta:
        ordering = ["sequence_order"]

    def __str__(self):
        return f"{self.name} [{self.plan_project_team}]"


class PlanPhaseSegment(models.Model):
    SEGMENT_RAMP = "RAMP"
    SEGMENT_FLAT = "FLAT"
    SEGMENT_CHOICES = [
        (SEGMENT_RAMP, "Ramp"),
        (SEGMENT_FLAT, "Flat"),
    ]

    PROG_LINEAR = "LINEAR"
    PROG_EXPONENTIAL = "EXPONENTIAL"
    PROG_LOGARITHMIC = "LOGARITHMIC"
    PROG_STEPPED = "STEPPED"
    PROG_FLAT = "FLAT"
    PROG_CHOICES = [
        (PROG_LINEAR, "Linear"),
        (PROG_EXPONENTIAL, "Exponential"),
        (PROG_LOGARITHMIC, "Logarithmic"),
        (PROG_STEPPED, "Stepped"),
        (PROG_FLAT, "Flat"),
    ]

    phase = models.ForeignKey(PlanPhase, on_delete=models.CASCADE, related_name="segments")
    segment_order = models.PositiveIntegerField()
    segment_type = models.CharField(max_length=10, choices=SEGMENT_CHOICES)
    start_pct = models.DecimalField(max_digits=5, decimal_places=2)
    end_pct = models.DecimalField(max_digits=5, decimal_places=2)
    progression = models.CharField(max_length=20, choices=PROG_CHOICES, default=PROG_LINEAR)
    duration = models.PositiveIntegerField()
    step_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("phase", "segment_order")]
        ordering = ["segment_order"]

    def __str__(self):
        return f"Segment {self.segment_order} of {self.phase.name}"


class PlanPhaseDependency(models.Model):
    DEP_SS = "SS"
    DEP_FS = "FS"
    DEP_FF = "FF"
    DEP_SF = "SF"
    DEP_CHOICES = [
        (DEP_SS, "Start-to-Start"),
        (DEP_FS, "Finish-to-Start"),
        (DEP_FF, "Finish-to-Finish"),
        (DEP_SF, "Start-to-Finish"),
    ]

    phase = models.ForeignKey(PlanPhase, on_delete=models.CASCADE, related_name="dependencies")
    predecessor_phase = models.ForeignKey(
        PlanPhase, on_delete=models.PROTECT, related_name="successor_dependencies"
    )
    dependency_type = models.CharField(max_length=2, choices=DEP_CHOICES)
    lag_sprints = models.IntegerField(default=0)

    class Meta:
        unique_together = [("phase", "predecessor_phase")]
        ordering = ["id"]

    def __str__(self):
        return f"{self.predecessor_phase.name} → {self.phase.name} [{self.dependency_type}]"


class PlanPhasePause(models.Model):
    INPUT_SPRINT = "SPRINT"
    INPUT_COUNT = "COUNT"
    INPUT_CHOICES = [
        (INPUT_SPRINT, "Sprint"),
        (INPUT_COUNT, "Count"),
    ]

    phase = models.ForeignKey(PlanPhase, on_delete=models.CASCADE, related_name="pauses")
    pause_from = models.ForeignKey(
        "sprints.Sprint", on_delete=models.PROTECT, related_name="+"
    )
    input_mode = models.CharField(max_length=10, choices=INPUT_CHOICES)
    pause_until_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    pause_sprint_count = models.PositiveIntegerField(null=True, blank=True)
    resume_sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    is_beyond_fy = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = [("phase", "pause_from")]
        ordering = ["pause_from__sprint_number"]

    def __str__(self):
        return f"Pause from {self.pause_from.sprint_name} [{self.phase.name}]"


class PlanAssignment(models.Model):
    ASSIGN_ENGINEER = "ENGINEER"
    ASSIGN_ARCHITECT = "ARCHITECT"
    ASSIGN_ADHOC = "ADHOC"
    ASSIGN_INTERIM = "INTERIM"
    ASSIGN_CHOICES = [
        (ASSIGN_ENGINEER, "Engineer"),
        (ASSIGN_ARCHITECT, "Architect"),
        (ASSIGN_ADHOC, "Ad-hoc"),
        (ASSIGN_INTERIM, "Interim"),
    ]

    phase = models.ForeignKey(PlanPhase, on_delete=models.CASCADE, related_name="assignments")
    # Null when auto_assign=True; engine fills it later
    team_member = models.ForeignKey(
        "team_members.TeamMember",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    auto_assign = models.BooleanField(default=False)
    assignment_type = models.CharField(
        max_length=20, choices=ASSIGN_CHOICES, default=ASSIGN_ENGINEER
    )
    # INTERIM only: who this assignment covers for
    replaces_member = models.ForeignKey(
        "team_members.TeamMember",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # INTERIM only: how many sprints this interim covers
    interim_sprint_count = models.PositiveIntegerField(null=True, blank=True)
    # Per-engineer share when split_mode=PERCENT (%) or DAYS
    split_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # Auto-set: ENGINEER=True, ARCHITECT/ADHOC/INTERIM=False
    includes_in_budget = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        label = self.team_member.display_name if self.team_member else "Auto"
        return f"{label} → {self.phase.name} [{self.assignment_type}]"


class PlaceholderLeave(models.Model):
    """
    Engine-generated estimated leave for a team member in a sprint, scoped to a plan version.
    Created during Step 2 (Full Run). Users can manually adjust days; is_auto becomes False.
    """

    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name="placeholder_leaves"
    )
    team_member = models.ForeignKey(
        "team_members.TeamMember", on_delete=models.CASCADE, related_name="placeholder_leaves"
    )
    sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.CASCADE, related_name="placeholder_leaves"
    )
    days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_auto = models.BooleanField(default=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("version", "team_member", "sprint")]
        ordering = ["sprint__sprint_number", "team_member__last_name"]

    def __str__(self):
        return f"PlaceholderLeave {self.team_member} S{self.sprint.sprint_number}: {self.days}d"


class ResourcePlanComment(models.Model):
    plan = models.ForeignKey(
        ResourcePlan, on_delete=models.CASCADE, related_name="comments"
    )
    comment = models.TextField()
    posted_by = models.CharField(max_length=200, default="Anonymous")
    posted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='resource_plan_comments',
    )
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='resource_plan_comment_mentions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment on {self.plan.name} @ {self.created_at:%Y-%m-%d %H:%M}"


class ResourcePlanCommentAttachment(models.Model):
    """File attachments on resource plan comments."""
    comment      = models.ForeignKey(ResourcePlanComment, on_delete=models.CASCADE, related_name='attachments')
    file_name    = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, default='')
    file_size    = models.PositiveBigIntegerField(default=0)
    file_data    = models.BinaryField(blank=True, null=True)
    file_path    = models.CharField(max_length=1000, blank=True, default='')
    s3_key       = models.CharField(max_length=1000, blank=True, default='')
    uploaded_by  = models.CharField(max_length=200, default='')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.file_name} (rp comment {self.comment_id})'


class ResourcePlanMemberCapacity(models.Model):
    """
    Materialised per-member sprint capacity for a plan version.
    Synced from SprintCapacity + PlaceholderLeave by the engine (or on PL edit).
    Net capacity = working_days − holiday_days − leave_days − placeholder_days.
    """

    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name="member_capacities"
    )
    team_member = models.ForeignKey(
        "team_members.TeamMember", on_delete=models.CASCADE, related_name="rp_capacities"
    )
    sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.CASCADE, related_name="rp_capacities"
    )
    working_days    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    holiday_days    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_days      = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    placeholder_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    net_capacity    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("version", "team_member", "sprint")]
        ordering = ["sprint__sprint_number", "team_member__last_name"]

    def __str__(self):
        return f"{self.team_member} — {self.sprint} (net: {self.net_capacity}d)"


class PlanEngineJob(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_RUNNING = "RUNNING"
    STATUS_COMPLETE = "COMPLETE"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    ]

    MODE_VALIDATE = "VALIDATE"
    MODE_FULL = "FULL"
    MODE_CHOICES = [
        (MODE_VALIDATE, "Validate Only"),
        (MODE_FULL, "Full Run"),
    ]

    plan = models.ForeignKey(ResourcePlan, on_delete=models.CASCADE, related_name="engine_jobs")
    version = models.ForeignKey(ResourcePlanVersion, on_delete=models.CASCADE, related_name="engine_jobs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_VALIDATE)
    current_step = models.CharField(max_length=100, null=True, blank=True)
    progress_pct = models.PositiveIntegerField(default=0)
    include_current_sprint = models.BooleanField(default=False)
    dry_run = models.BooleanField(default=False)
    remove_overrides = models.BooleanField(default=False)
    initiated_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    validation_result = models.JSONField(null=True, blank=True)
    steps_log = models.JSONField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-initiated_at"]

    def __str__(self):
        return f"EngineJob #{self.pk} [{self.mode}] {self.status} – {self.plan.name}"


class ResourcePlanPlaceholderEngineer(models.Model):
    """
    A virtual engineer slot created by the engine for auto-assigned phases.
    Replaced by a real TeamMember once a hire is confirmed.
    """

    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name="placeholder_engineers"
    )
    team = models.ForeignKey(
        "delivery_teams.DeliveryTeam", on_delete=models.PROTECT, related_name="+"
    )
    phase = models.ForeignKey(
        PlanPhase, on_delete=models.PROTECT, null=True, blank=True, related_name="placeholder_engineers"
    )
    slot_number = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=100)
    assignment_type = models.CharField(
        max_length=20,
        choices=PlanAssignment.ASSIGN_CHOICES,
        default=PlanAssignment.ASSIGN_ENGINEER,
    )

    class Meta:
        unique_together = [("version", "team", "slot_number")]
        ordering = ["team__name", "slot_number"]

    def __str__(self):
        return f"{self.name} (placeholder — {self.team.name})"


class ResourcePlanAllocationSet(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUPERSEDED = "SUPERSEDED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name="allocation_sets"
    )
    engine_job = models.ForeignKey(
        PlanEngineJob, on_delete=models.PROTECT, null=True, blank=True, related_name="allocation_sets"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    activated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AllocationSet #{self.pk} [{self.status}] v{self.version.version}"


class ResourcePlanAllocation(models.Model):
    """
    Atomic allocation cell: one engineer (or placeholder) × project × sprint.
    Exactly one of team_member / placeholder_engineer must be set.
    """

    allocation_set = models.ForeignKey(
        ResourcePlanAllocationSet, on_delete=models.CASCADE, related_name="allocations"
    )
    programme = models.ForeignKey(
        "programmes.Programme", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="+"
    )
    team = models.ForeignKey(
        "delivery_teams.DeliveryTeam", on_delete=models.PROTECT, related_name="+"
    )
    team_member = models.ForeignKey(
        "team_members.TeamMember", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    placeholder_engineer = models.ForeignKey(
        ResourcePlanPlaceholderEngineer, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    sprint = models.ForeignKey(
        "sprints.Sprint", on_delete=models.PROTECT, related_name="+"
    )
    phase = models.ForeignKey(
        PlanPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assignment = models.ForeignKey(
        PlanAssignment, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    assignment_type = models.CharField(max_length=20, choices=PlanAssignment.ASSIGN_CHOICES)
    includes_in_budget = models.BooleanField(default=True)
    engine_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    override_days = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    override_notes = models.TextField(null=True, blank=True)
    overridden_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sprint__sprint_number"]

    @property
    def effective_days(self):
        return self.override_days if self.override_days is not None else self.engine_days

    def __str__(self):
        who = (
            self.team_member.display_name
            if self.team_member
            else (self.placeholder_engineer.name if self.placeholder_engineer else "?")
        )
        return f"{who} — {self.project.name} — {self.sprint} ({self.effective_days}d)"


class Conflict(models.Model):
    # Conflict types
    CAPACITY_EXCEEDED    = 'CAPACITY_EXCEEDED'
    COMPETING_PRIORITY   = 'COMPETING_PRIORITY'
    TIMELINE_BREACH      = 'TIMELINE_BREACH'
    BUDGET_EXCEEDED      = 'BUDGET_EXCEEDED'
    DEPENDENCY_VIOLATED  = 'DEPENDENCY_VIOLATED'
    UNRESOLVABLE_GAP     = 'UNRESOLVABLE_GAP'
    THRESHOLD_BREACH     = 'THRESHOLD_BREACH'
    CONFLICT_TYPE_CHOICES = [
        (CAPACITY_EXCEEDED,   'Capacity Exceeded'),
        (COMPETING_PRIORITY,  'Competing Priority'),
        (TIMELINE_BREACH,     'Timeline Breach'),
        (BUDGET_EXCEEDED,     'Budget Exceeded'),
        (DEPENDENCY_VIOLATED, 'Dependency Violated'),
        (UNRESOLVABLE_GAP,    'Unresolvable Gap'),
        (THRESHOLD_BREACH,    'Threshold Breach'),
    ]

    # Severity
    SEVERITY_ERROR   = 'ERROR'
    SEVERITY_WARNING = 'WARNING'
    SEVERITY_INFO    = 'INFO'
    SEVERITY_CHOICES = [
        (SEVERITY_ERROR,   'Error'),
        (SEVERITY_WARNING, 'Warning'),
        (SEVERITY_INFO,    'Info'),
    ]

    # Status
    STATUS_OPEN      = 'OPEN'
    STATUS_RESOLVED  = 'RESOLVED'
    STATUS_DISMISSED = 'DISMISSED'
    STATUS_CHOICES   = [
        (STATUS_OPEN,      'Open'),
        (STATUS_RESOLVED,  'Resolved'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    # Resolution types
    RES_DEPRIORITISED    = 'DEPRIORITISED'
    RES_TIMELINE_SHIFTED = 'TIMELINE_SHIFTED'
    RES_ENGINEER_SWAPPED = 'ENGINEER_SWAPPED'
    RES_TEAM_CHANGED     = 'TEAM_CHANGED'
    RES_MANPOWER_RAISED  = 'MANPOWER_RAISED'
    RES_REBALANCED       = 'REBALANCED'
    RES_DISMISSED        = 'DISMISSED'
    RESOLUTION_TYPE_CHOICES = [
        (RES_DEPRIORITISED,    'Deprioritised'),
        (RES_TIMELINE_SHIFTED, 'Timeline Shifted'),
        (RES_ENGINEER_SWAPPED, 'Engineer Swapped'),
        (RES_TEAM_CHANGED,     'Team Changed'),
        (RES_MANPOWER_RAISED,  'Manpower Raised'),
        (RES_REBALANCED,       'Rebalanced'),
        (RES_DISMISSED,        'Dismissed'),
    ]

    allocation_set     = models.ForeignKey(ResourcePlanAllocationSet, on_delete=models.CASCADE, related_name='conflicts')
    engine_job         = models.ForeignKey(PlanEngineJob, on_delete=models.CASCADE, null=True, blank=True, related_name='conflicts')
    conflict_type      = models.CharField(max_length=30, choices=CONFLICT_TYPE_CHOICES)
    severity           = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default=SEVERITY_ERROR)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    affected_project   = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    affected_phase     = models.ForeignKey(PlanPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name='conflicts')
    affected_team_member = models.ForeignKey('team_members.TeamMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    affected_sprint    = models.ForeignKey('sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    affected_team      = models.ForeignKey('delivery_teams.DeliveryTeam', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    description        = models.TextField()
    engine_data        = models.JSONField(default=dict)
    resolution_type    = models.CharField(max_length=30, choices=RESOLUTION_TYPE_CHOICES, null=True, blank=True)
    resolution_notes   = models.TextField(null=True, blank=True)
    resolved_at        = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    SEVERITY_ORDER = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

    class Meta:
        ordering = ['status', 'severity', 'conflict_type', '-created_at']

    def __str__(self):
        return f'{self.conflict_type} [{self.severity}] — {self.allocation_set}'


class ManpowerRequest(models.Model):
    STATUS_OPEN       = 'OPEN'
    STATUS_HIRING     = 'HIRING'
    STATUS_REBALANCED = 'REBALANCED'
    STATUS_DISMISSED  = 'DISMISSED'
    STATUS_CHOICES    = [
        (STATUS_OPEN,       'Open'),
        (STATUS_HIRING,     'Hiring'),
        (STATUS_REBALANCED, 'Rebalanced'),
        (STATUS_DISMISSED,  'Dismissed'),
    ]

    allocation_set   = models.ForeignKey(ResourcePlanAllocationSet, on_delete=models.CASCADE, related_name='manpower_requests')
    conflict         = models.ForeignKey(Conflict, on_delete=models.CASCADE, related_name='manpower_requests')
    team             = models.ForeignKey('delivery_teams.DeliveryTeam', on_delete=models.PROTECT, related_name='+')
    phase            = models.ForeignKey(PlanPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name='manpower_requests')
    sprints_needed   = models.PositiveIntegerField()
    days_needed      = models.DecimalField(max_digits=6, decimal_places=2)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    resolution_notes = models.TextField(null=True, blank=True)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'ManpowerRequest {self.team.name} — {self.days_needed}d [{self.status}]'


class PlaceholderEngineer(models.Model):
    """
    A user-initiated hire placeholder created from a ManpowerRequest.
    Represents a future engineer slot from onboard_sprint onwards.
    """
    version = models.ForeignKey(
        ResourcePlanVersion, on_delete=models.CASCADE, related_name='hire_placeholders'
    )
    sequence_number = models.PositiveIntegerField()
    display_name = models.CharField(max_length=50)
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam', on_delete=models.PROTECT, related_name='+'
    )
    manpower_request = models.ForeignKey(
        ManpowerRequest, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='placeholder_engineers'
    )
    onboard_sprint = models.ForeignKey(
        'sprints.Sprint', on_delete=models.PROTECT, related_name='+',
        null=True, blank=True,
    )
    engine_suggested_sprint = models.ForeignKey(
        'sprints.Sprint', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    capacity_days_per_sprint = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    replaced_by = models.ForeignKey(
        'team_members.TeamMember', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    replaced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('version', 'sequence_number')]
        ordering = ['sequence_number']

    def __str__(self):
        return f'{self.display_name} ({self.team.name})'


class PlaceholderEngineerAbsence(models.Model):
    """Per-sprint absence for a hire placeholder. effective_days = override_days if set, else days."""
    placeholder_engineer = models.ForeignKey(
        PlaceholderEngineer, on_delete=models.CASCADE, related_name='absences'
    )
    sprint = models.ForeignKey(
        'sprints.Sprint', on_delete=models.PROTECT, related_name='+'
    )
    days = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    is_engine_generated = models.BooleanField(default=True)
    override_days = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    override_notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = [('placeholder_engineer', 'sprint')]
        ordering = ['sprint__sprint_number']

    @property
    def effective_days(self):
        return self.override_days if self.override_days is not None else self.days

    def __str__(self):
        return f'{self.placeholder_engineer.display_name} — {self.sprint}: {self.effective_days}d'


# ── Phase 12: Snapshots ───────────────────────────────────────────────────────


class ResourcePlanSnapshot(models.Model):
    STATUS_PENDING     = 'PENDING'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETE    = 'COMPLETE'
    STATUS_FAILED      = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING,     'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETE,    'Complete'),
        (STATUS_FAILED,      'Failed'),
    ]

    version      = models.ForeignKey(ResourcePlanVersion, on_delete=models.CASCADE, related_name='snapshots')
    label        = models.CharField(max_length=200)
    notes        = models.TextField(null=True, blank=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Summary metrics populated on completion
    total_allocation_days = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_members         = models.PositiveIntegerField(null=True, blank=True)
    total_projects        = models.PositiveIntegerField(null=True, blank=True)
    total_sprints         = models.PositiveIntegerField(null=True, blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log    = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-initiated_at']

    def __str__(self):
        return f'Snapshot "{self.label}" [{self.status}] — {self.version}'


class ResourcePlanSnapshotAllocation(models.Model):
    """Denormalised, point-in-time copy of allocation rows. Name fields are stable after rename."""
    snapshot         = models.ForeignKey(ResourcePlanSnapshot, on_delete=models.CASCADE, related_name='allocations')
    sprint_number    = models.PositiveIntegerField()
    sprint_name      = models.CharField(max_length=100)
    member_name      = models.CharField(max_length=200)
    team_name        = models.CharField(max_length=200)
    project_name     = models.CharField(max_length=200)
    programme_name   = models.CharField(max_length=200, null=True, blank=True)
    phase_name       = models.CharField(max_length=200, null=True, blank=True)
    assignment_type  = models.CharField(max_length=20)
    includes_in_budget = models.BooleanField(default=True)
    days             = models.DecimalField(max_digits=6, decimal_places=2)
    is_override      = models.BooleanField(default=False)
    is_placeholder   = models.BooleanField(default=False)

    class Meta:
        ordering = ['sprint_number', 'team_name', 'member_name']


class ResourcePlanSnapshotCapacity(models.Model):
    """Denormalised, point-in-time copy of member capacity rows."""
    snapshot         = models.ForeignKey(ResourcePlanSnapshot, on_delete=models.CASCADE, related_name='capacities')
    sprint_number    = models.PositiveIntegerField()
    sprint_name      = models.CharField(max_length=100)
    member_name      = models.CharField(max_length=200)
    team_name        = models.CharField(max_length=200)
    working_days     = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    holiday_days     = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_days       = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    placeholder_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    net_capacity     = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ['sprint_number', 'team_name', 'member_name']


# ── Phase 13: Audit Log ───────────────────────────────────────────────────────


class AuditLog(models.Model):
    EVENT_ENGINE_RUN            = 'ENGINE_RUN'
    EVENT_ALLOCATION_OVERRIDE   = 'ALLOCATION_OVERRIDE'
    EVENT_PLACEHOLDER_OVERRIDE  = 'PLACEHOLDER_OVERRIDE'
    EVENT_CONFLICT_RESOLVED     = 'CONFLICT_RESOLVED'
    EVENT_STATUS_CHANGED        = 'STATUS_CHANGED'
    EVENT_PLAN_CLONED           = 'PLAN_CLONED'
    EVENT_CONFIG_CHANGED        = 'CONFIG_CHANGED'
    EVENT_TYPE_CHOICES = [
        (EVENT_ENGINE_RUN,           'Engine Run'),
        (EVENT_ALLOCATION_OVERRIDE,  'Allocation Override'),
        (EVENT_PLACEHOLDER_OVERRIDE, 'Placeholder Override'),
        (EVENT_CONFLICT_RESOLVED,    'Conflict Resolved'),
        (EVENT_STATUS_CHANGED,       'Status Changed'),
        (EVENT_PLAN_CLONED,          'Plan Cloned'),
        (EVENT_CONFIG_CHANGED,       'Config Changed'),
    ]

    plan         = models.ForeignKey(ResourcePlan, on_delete=models.CASCADE, related_name='audit_logs')
    version      = models.ForeignKey(ResourcePlanVersion, on_delete=models.CASCADE, related_name='audit_logs')
    event_type   = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    entity_type  = models.CharField(max_length=30)
    entity_id    = models.PositiveIntegerField(null=True, blank=True)
    before_state = models.JSONField(null=True, blank=True)
    after_state  = models.JSONField(null=True, blank=True)
    engine_job   = models.ForeignKey(
        PlanEngineJob, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs'
    )
    notes        = models.TextField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} — {self.entity_type}#{self.entity_id} [{self.created_at:%Y-%m-%d %H:%M}]'
