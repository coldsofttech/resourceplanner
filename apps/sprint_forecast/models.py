from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.db import models

User = get_user_model()

_CODE_VALIDATOR = RegexValidator(
    regex=r'^[A-Z][A-Z0-9_]*$',
    message='Code must be UPPER_SNAKE_CASE (e.g. PROJECT, BAU, HOLIDAY).',
)

RECHARGE_TYPE_FORECAST = 'FORECAST'
RECHARGE_TYPE_ACTUAL = 'ACTUAL'
RECHARGE_TYPE_CHOICES = [
    (RECHARGE_TYPE_FORECAST, 'Forecast'),
    (RECHARGE_TYPE_ACTUAL, 'Actual'),
]

IMPORT_TYPE_FORECAST = 'FORECAST'
IMPORT_TYPE_ACTUAL = 'ACTUAL'
IMPORT_TYPE_CHOICES = [
    (IMPORT_TYPE_FORECAST, 'Forecast'),
    (IMPORT_TYPE_ACTUAL, 'Actual'),
]

IMPORT_STATUS_ACTIVE = 'active'
IMPORT_STATUS_SUPERSEDED = 'superseded'
IMPORT_STATUS_CONFIRMED = 'confirmed'
IMPORT_STATUS_CHOICES = [
    (IMPORT_STATUS_ACTIVE, 'Active'),
    (IMPORT_STATUS_SUPERSEDED, 'Superseded'),
    (IMPORT_STATUS_CONFIRMED, 'Confirmed'),
]

CHECK_LABEL = 'label_check'
CHECK_MAPPING = 'mapping_check'
CHECK_CAPACITY = 'capacity_check'
CHECK_TYPE_CHOICES = [
    (CHECK_LABEL, 'Label Check'),
    (CHECK_MAPPING, 'Mapping Check'),
    (CHECK_CAPACITY, 'Capacity Check'),
]

CHECK_PASS = 'pass'
CHECK_ERROR = 'error'
CHECK_STATUS_CHOICES = [
    (CHECK_PASS, 'Pass'),
    (CHECK_ERROR, 'Error'),
]


class ProjectFinanceType(models.Model):
    """Finance type used for sprint import mapping (e.g. PROJECT, BAU, HOLIDAY)."""
    code = models.CharField(
        max_length=50,
        unique=True,
        validators=[_CODE_VALIDATOR],
        help_text='Unique UPPER_SNAKE_CASE code, e.g. PROJECT, BAU, HOLIDAY.',
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'


class ProjectFinanceTypeMapping(models.Model):
    """Allowed finance types per project type."""
    project_type = models.ForeignKey(
        'project_types.ProjectType',
        on_delete=models.CASCADE,
        related_name='finance_type_mappings',
    )
    finance_type = models.ForeignKey(
        ProjectFinanceType,
        on_delete=models.CASCADE,
        related_name='project_type_mappings',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['project_type', 'finance_type']
        constraints = [
            models.UniqueConstraint(
                fields=['project_type', 'finance_type'],
                name='unique_project_finance_type_mapping',
            )
        ]

    def __str__(self):
        return f'{self.project_type} → {self.finance_type.code}'


class SprintImport(models.Model):
    """One CSV upload per team per sprint. Versioned — new upload creates new version."""
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='sprint_imports',
    )
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.CASCADE,
        related_name='sprint_imports',
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=IMPORT_STATUS_CHOICES,
        default=IMPORT_STATUS_ACTIVE,
    )
    import_type = models.CharField(
        max_length=10,
        choices=IMPORT_TYPE_CHOICES,
        default=IMPORT_TYPE_FORECAST,
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sprint_imports',
    )

    class Meta:
        ordering = ['sprint', 'team', 'version_number']
        constraints = [
            models.UniqueConstraint(
                fields=['sprint', 'team', 'import_type', 'version_number'],
                name='unique_sprint_import_version',
            )
        ]

    def __str__(self):
        return f'{self.sprint} / {self.team} — v{self.version_number} ({self.import_type}/{self.status})'


class SprintImportRow(models.Model):
    """One row from the imported CSV. Override fields store user edits."""
    sprint_import = models.ForeignKey(
        SprintImport,
        on_delete=models.CASCADE,
        related_name='rows',
    )
    order = models.PositiveIntegerField(default=0)
    is_manually_added = models.BooleanField(default=False)

    # ── Original values from CSV ──────────────────────────────────────────────
    story_type = models.CharField(max_length=200, blank=True)
    jira_id = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=500, blank=True)
    assignee_raw = models.CharField(max_length=300, blank=True)
    assignee = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_rows',
    )
    efforts_ms = models.BigIntegerField(default=0)
    sprint_name = models.CharField(max_length=200, blank=True)
    label_raw = models.CharField(max_length=200, blank=True)
    label = models.ForeignKey(
        'projects.ProjectLabel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_rows',
    )
    mapping_raw = models.CharField(max_length=100, blank=True)
    mapping = models.ForeignKey(
        ProjectFinanceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_rows',
    )

    # ── Override fields (null = not overridden) ───────────────────────────────
    story_type_override = models.CharField(max_length=200, null=True, blank=True)
    jira_id_override = models.CharField(max_length=100, null=True, blank=True)
    title_override = models.CharField(max_length=500, null=True, blank=True)
    assignee_raw_override = models.CharField(max_length=300, null=True, blank=True)
    assignee_override = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_row_overrides',
    )
    efforts_ms_override = models.BigIntegerField(null=True, blank=True)
    sprint_name_override = models.CharField(max_length=200, null=True, blank=True)
    label_override = models.ForeignKey(
        'projects.ProjectLabel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_row_overrides',
    )
    mapping_override = models.ForeignKey(
        ProjectFinanceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_row_overrides',
    )

    class Meta:
        ordering = ['sprint_import', 'order']

    def __str__(self):
        return f'Import {self.sprint_import_id} row {self.order}: {self.effective_jira_id or "(no jira)"}'

    # ── Effective value helpers ───────────────────────────────────────────────
    @property
    def effective_story_type(self):
        return self.story_type_override if self.story_type_override is not None else self.story_type

    @property
    def effective_jira_id(self):
        return self.jira_id_override if self.jira_id_override is not None else self.jira_id

    @property
    def effective_title(self):
        return self.title_override if self.title_override is not None else self.title

    @property
    def effective_assignee_raw(self):
        return self.assignee_raw_override if self.assignee_raw_override is not None else self.assignee_raw

    @property
    def effective_assignee(self):
        return self.assignee_override if self.assignee_override is not None else self.assignee

    @property
    def effective_efforts_ms(self):
        return self.efforts_ms_override if self.efforts_ms_override is not None else self.efforts_ms

    @property
    def effective_sprint_name(self):
        return self.sprint_name_override if self.sprint_name_override is not None else self.sprint_name

    @property
    def effective_label(self):
        return self.label_override if self.label_override is not None else self.label

    @property
    def effective_mapping(self):
        return self.mapping_override if self.mapping_override is not None else self.mapping

    def compute_days(self, hours_per_day=7):
        ms = self.effective_efforts_ms or 0
        if ms <= 0 or hours_per_day <= 0:
            return 0
        from decimal import Decimal, ROUND_HALF_UP
        ms_per_day = hours_per_day * 3_600_000
        return (Decimal(ms) / Decimal(ms_per_day)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def has_overrides(self):
        return any([
            self.story_type_override is not None,
            self.jira_id_override is not None,
            self.title_override is not None,
            self.assignee_raw_override is not None,
            self.assignee_override_id is not None,
            self.efforts_ms_override is not None,
            self.sprint_name_override is not None,
            self.label_override_id is not None,
            self.mapping_override_id is not None,
        ])


class ImportReview(models.Model):
    """One review run against a SprintImport."""
    sprint_import = models.ForeignKey(
        SprintImport,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    reviewed_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_reviews',
    )

    class Meta:
        ordering = ['-reviewed_at']

    def __str__(self):
        return f'Review for import {self.sprint_import_id} at {self.reviewed_at}'


class ImportReviewResult(models.Model):
    """Per-row per-check result from a review run."""
    review = models.ForeignKey(
        ImportReview,
        on_delete=models.CASCADE,
        related_name='results',
    )
    row = models.ForeignKey(
        SprintImportRow,
        on_delete=models.CASCADE,
        related_name='review_results',
    )
    check_type = models.CharField(max_length=30, choices=CHECK_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=CHECK_STATUS_CHOICES)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ['review', 'row__order', 'check_type']

    def __str__(self):
        return f'{self.check_type} → {self.status} (row {self.row_id})'


class SprintConfirmedRow(models.Model):
    """Confirmed snapshot written when a team confirms their import version."""
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='confirmed_rows',
    )
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.CASCADE,
        related_name='sprint_confirmed_rows',
    )
    sprint_import = models.ForeignKey(
        SprintImport,
        on_delete=models.CASCADE,
        related_name='confirmed_rows',
    )
    import_type = models.CharField(
        max_length=10,
        choices=IMPORT_TYPE_CHOICES,
        default=IMPORT_TYPE_FORECAST,
    )
    story_type = models.CharField(max_length=200, blank=True)
    jira_id = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=500, blank=True)
    assignee = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sprint_confirmed_rows',
    )
    assignee_raw = models.CharField(max_length=300, blank=True)
    efforts_ms = models.BigIntegerField(default=0)
    days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sprint_name = models.CharField(max_length=200, blank=True)
    label = models.ForeignKey(
        'projects.ProjectLabel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sprint_confirmed_rows',
    )
    label_raw = models.CharField(max_length=200, blank=True)
    mapping = models.ForeignKey(
        ProjectFinanceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sprint_confirmed_rows',
    )
    mapping_raw = models.CharField(max_length=100, blank=True)
    is_override = models.BooleanField(default=False)

    class Meta:
        ordering = ['sprint', 'team', 'sprint_import', 'id']

    def __str__(self):
        return f'{self.sprint} / {self.team} — {self.jira_id or "(manual)"}'


class SprintImportReviewComplete(models.Model):
    """Tracks sprint-level Review Complete for both forecast and actual imports."""
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='import_review_completions',
    )
    import_type = models.CharField(
        max_length=10,
        choices=IMPORT_TYPE_CHOICES,
        default=IMPORT_TYPE_FORECAST,
    )
    completed_at = models.DateTimeField(auto_now_add=True)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_review_completions',
    )
    override_applied = models.BooleanField(default=False)
    override_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sprint', 'import_type'],
                name='unique_sprint_import_review_complete',
            )
        ]

    def __str__(self):
        return f'{self.import_type} review complete for {self.sprint}'


class RechargeDetail(models.Model):
    """Low-level recharge: one row per (sprint, team, engineer, programme, project, label)."""
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='recharge_details',
    )
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.CASCADE,
        related_name='recharge_details',
    )
    assignee = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recharge_details',
    )
    programme = models.ForeignKey(
        'programmes.Programme',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recharge_details',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recharge_details',
    )
    label = models.ForeignKey(
        'projects.ProjectLabel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recharge_details',
    )
    type = models.CharField(max_length=10, choices=RECHARGE_TYPE_CHOICES, default=RECHARGE_TYPE_FORECAST)
    total_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sprint_import = models.ForeignKey(
        SprintImport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recharge_details',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sprint', 'team', 'assignee']

    def __str__(self):
        return f'{self.sprint} / {self.assignee} — {self.project} ({self.type})'


class Recharge(models.Model):
    """Aggregated recharge: one row per (sprint, type, programme, project)."""
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='recharges',
    )
    type = models.CharField(max_length=10, choices=RECHARGE_TYPE_CHOICES, default=RECHARGE_TYPE_FORECAST)
    programme = models.ForeignKey(
        'programmes.Programme',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recharges',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recharges',
    )
    total_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    finance_contacts = models.ManyToManyField(
        'projects.ProjectContact',
        blank=True,
        related_name='recharges_as_finance',
        limit_choices_to={'role': 'FINANCE'},
    )
    project_contacts = models.ManyToManyField(
        'projects.ProjectContact',
        blank=True,
        related_name='recharges_as_project',
        limit_choices_to={'role': 'PROJECT'},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sprint', 'type', 'programme', 'project']
        constraints = [
            models.UniqueConstraint(
                fields=['sprint', 'type', 'programme', 'project'],
                name='unique_recharge_per_sprint_project',
            )
        ]

    def __str__(self):
        proj = self.project.name if self.project else '—'
        return f'{self.sprint} / {proj} ({self.type})'


RISK_NEUTRAL = 'NEUTRAL'
RISK_WARNING = 'WARNING'
RISK_RISK = 'RISK'


class ProjectActuals(models.Model):
    """Aggregated actuals per project, updated each time a sprint is closed."""
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='actuals',
    )
    programme = models.ForeignKey(
        'programmes.Programme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_actuals',
    )
    label = models.ForeignKey(
        'projects.ProjectLabel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_actuals',
    )
    code = models.CharField(max_length=255, blank=True)
    assigned_team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_actuals',
    )
    collaborators = models.ManyToManyField(
        'delivery_teams.DeliveryTeam',
        related_name='collaborating_project_actuals',
        blank=True,
    )
    estimate_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estimate_value_with_contingency = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cost_till_date = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_updated_sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_project_actuals',
    )
    ignore_risk = models.BooleanField(
        default=False,
        help_text='When True, this project is excluded from risk calculations and treated as Neutral.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project']

    def __str__(self):
        return f'Actuals — {self.project}'

    @property
    def remaining_amount(self):
        total = self.total_cost_till_date
        if total <= self.estimate_value:
            return self.estimate_value - total
        return self.estimate_value_with_contingency - total

    @property
    def risk(self):
        if self.ignore_risk:
            return RISK_NEUTRAL
        total = self.total_cost_till_date
        if total < self.estimate_value:
            return RISK_NEUTRAL
        if total <= self.estimate_value_with_contingency:
            return RISK_WARNING
        return RISK_RISK


class ProjectSprintActual(models.Model):
    """Per-sprint cost breakdown linked to a ProjectActuals record."""
    project_actuals = models.ForeignKey(
        ProjectActuals,
        on_delete=models.CASCADE,
        related_name='sprint_actuals',
    )
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='project_sprint_actuals',
    )
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ['sprint__sprint_number']
        constraints = [
            models.UniqueConstraint(
                fields=['project_actuals', 'sprint'],
                name='unique_project_sprint_actual',
            )
        ]

    def __str__(self):
        return f'{self.project_actuals} — {self.sprint}'


class RechargeStory(models.Model):
    """Individual Jira stories linked to an aggregate Recharge (for future email use)."""
    recharge = models.ForeignKey(
        Recharge,
        on_delete=models.CASCADE,
        related_name='stories',
    )
    jira_id = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=500, blank=True)
    total_days = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ['recharge', 'jira_id']

    def __str__(self):
        return f'{self.recharge_id} — {self.jira_id or "(no jira)"}'
