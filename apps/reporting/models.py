from django.conf import settings
from django.db import models


class Report(models.Model):
    STANDARD = "STANDARD"
    CUSTOM = "CUSTOM"
    REPORT_TYPE_CHOICES = [
        (STANDARD, "Standard"),
        (CUSTOM, "Custom"),
    ]

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(
        max_length=20, choices=REPORT_TYPE_CHOICES, default=STANDARD
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_reports",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_reports",
    )

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class DemandCapacityConfig(models.Model):
    plan = models.ForeignKey(
        "resource_plans.ResourcePlan",
        on_delete=models.CASCADE,
        related_name="demand_capacity_configs",
    )
    version = models.ForeignKey(
        "resource_plans.ResourcePlanVersion",
        on_delete=models.CASCADE,
        related_name="demand_capacity_configs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_demand_capacity_configs",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_demand_capacity_configs",
    )

    class Meta:
        unique_together = [("plan", "version")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"D&C Config — {self.plan.name} v{self.version.version}"


class ProgrammeCategoryMapping(models.Model):
    config = models.ForeignKey(
        DemandCapacityConfig,
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    programme = models.ForeignKey(
        "programmes.Programme",
        on_delete=models.PROTECT,
        related_name="category_mappings",
    )
    category_label = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_programme_category_mappings",
    )

    class Meta:
        unique_together = [("config", "programme")]
        ordering = ["programme__name"]

    def __str__(self):
        return f"{self.programme.name} → {self.category_label}"


class KPIReportComment(models.Model):
    """Per-project comment for a specific month's KPI Estimate % Accuracy report."""

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="kpi_comments",
    )
    month = models.CharField(
        max_length=7,
        help_text="Month in YYYY-MM format (e.g. 2025-03).",
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_kpi_comments",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_kpi_comments",
    )

    class Meta:
        ordering = ["project__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "month"],
                name="unique_kpi_comment_project_month",
            )
        ]

    def __str__(self):
        return f"KPI Comment — {self.project} ({self.month})"


class CustomReport(models.Model):
    CHART_TABLE       = 'table'
    CHART_PIVOT       = 'pivot'
    CHART_BAR         = 'bar'
    CHART_STACKED_BAR = 'stacked_bar'
    CHART_PIE         = 'pie'
    CHART_LINE        = 'line'
    CHART_HEATMAP     = 'heatmap'

    VISUALIZATION_CHOICES = [
        (CHART_TABLE,       'Table'),
        (CHART_PIVOT,       'Pivot'),
        (CHART_BAR,         'Bar Chart'),
        (CHART_STACKED_BAR, 'Stacked Bar Chart'),
        (CHART_PIE,         'Pie Chart'),
        (CHART_LINE,        'Line Chart'),
        (CHART_HEATMAP,     'Heatmap'),
    ]

    PERM_VIEW = 'view'
    PERM_EDIT = 'edit'

    name          = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    owner         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_custom_reports',
    )
    data_source   = models.CharField(max_length=100, blank=True)
    visualization = models.CharField(max_length=20, choices=VISUALIZATION_CHOICES, default=CHART_TABLE)
    # config: {fields, filters, axis, legend, rows, columns, values}
    config        = models.JSONField(default=dict, blank=True)
    is_shared     = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_custom_reports',
    )
    updated_at    = models.DateTimeField(auto_now=True)
    updated_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_custom_reports',
    )

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def can_view(self, user) -> bool:
        if user.is_staff or self.owner_id == user.pk:
            return True
        return self.shares.filter(user=user).exists()

    def can_edit(self, user) -> bool:
        if user.is_staff or self.owner_id == user.pk:
            return True
        return self.shares.filter(user=user, permission=CustomReport.PERM_EDIT).exists()


class CustomReportShare(models.Model):
    PERM_VIEW = 'view'
    PERM_EDIT = 'edit'
    PERMISSION_CHOICES = [(PERM_VIEW, 'View'), (PERM_EDIT, 'Edit')]

    report     = models.ForeignKey(CustomReport, on_delete=models.CASCADE, related_name='shares')
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='custom_report_shares',
    )
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default=PERM_VIEW)
    shared_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='shared_custom_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['report', 'user'], name='unique_custom_report_share')
        ]

    def __str__(self):
        return f"{self.report} → {self.user} ({self.permission})"
