from django.contrib import admin
from .models import (
    ResourcePlan,
    ResourcePlanVersion,
    ResourcePlanScope,
    ResourcePlanComment,
    ResourcePlanVersionProject,
    ResourcePlanVersionProjectTeam,
    ResourcePlanVersionProjectBudgetRelease,
)


class ResourcePlanVersionInline(admin.StackedInline):
    model = ResourcePlanVersion
    extra = 0
    readonly_fields = ["plan_group", "version", "cloned_from"]


class ResourcePlanCommentInline(admin.TabularInline):
    model = ResourcePlanComment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(ResourcePlan)
class ResourcePlanAdmin(admin.ModelAdmin):
    list_display = ["name", "plan_type", "is_active", "created_at"]
    list_filter = ["plan_type", "is_active"]
    search_fields = ["name"]
    inlines = [ResourcePlanVersionInline, ResourcePlanCommentInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ResourcePlanScope)
class ResourcePlanScopeAdmin(admin.ModelAdmin):
    list_display = ["plan_group", "financial_year", "project", "programme", "team"]
    search_fields = ["plan_group"]


@admin.register(ResourcePlanComment)
class ResourcePlanCommentAdmin(admin.ModelAdmin):
    list_display = ["plan", "posted_by", "created_at"]
    readonly_fields = ["created_at"]


class ResourcePlanVersionProjectTeamInline(admin.TabularInline):
    model = ResourcePlanVersionProjectTeam
    extra = 0
    readonly_fields = ["allocated_days"]


class ResourcePlanVersionProjectBudgetReleaseInline(admin.TabularInline):
    model = ResourcePlanVersionProjectBudgetRelease
    extra = 0


@admin.register(ResourcePlanVersionProject)
class ResourcePlanVersionProjectAdmin(admin.ModelAdmin):
    list_display = ["project", "version", "basis", "basis_amount", "days_required", "created_at"]
    list_filter = ["basis", "version__status"]
    search_fields = ["project__name"]
    readonly_fields = ["days_required", "is_over_threshold", "is_under_threshold",
                       "is_team_budget_mismatch", "is_percent_incomplete",
                       "basis_synced_at", "created_at", "updated_at"]
    inlines = [ResourcePlanVersionProjectTeamInline, ResourcePlanVersionProjectBudgetReleaseInline]
