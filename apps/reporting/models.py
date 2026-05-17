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
