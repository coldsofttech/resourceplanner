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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment on {self.plan.name} @ {self.created_at:%Y-%m-%d %H:%M}"


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
