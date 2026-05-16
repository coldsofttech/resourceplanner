from django.contrib import admin

from .models import (
    ForecastImport,
    ForecastImportRow,
    ForecastReview,
    ForecastReviewResult,
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    Recharge,
    RechargeDetail,
    RechargeStory,
    SprintForecastReviewComplete,
    SprintForecastRow,
)


@admin.register(ProjectFinanceType)
class ProjectFinanceTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(ProjectFinanceTypeMapping)
class ProjectFinanceTypeMappingAdmin(admin.ModelAdmin):
    list_display = ['project_type', 'finance_type', 'created_at']
    list_filter = ['finance_type']


class ForecastImportRowInline(admin.TabularInline):
    model = ForecastImportRow
    extra = 0
    fields = ['order', 'story_type', 'jira_id', 'title', 'assignee', 'efforts_ms', 'label', 'mapping', 'is_manually_added']
    readonly_fields = ['order']


@admin.register(ForecastImport)
class ForecastImportAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team', 'version_number', 'status', 'imported_at', 'imported_by']
    list_filter = ['status', 'sprint', 'team']
    inlines = [ForecastImportRowInline]


@admin.register(ForecastReview)
class ForecastReviewAdmin(admin.ModelAdmin):
    list_display = ['forecast_import', 'reviewed_at', 'reviewed_by']


@admin.register(ForecastReviewResult)
class ForecastReviewResultAdmin(admin.ModelAdmin):
    list_display = ['review', 'row', 'check_type', 'status', 'message']
    list_filter = ['check_type', 'status']


@admin.register(SprintForecastRow)
class SprintForecastRowAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team', 'jira_id', 'title', 'assignee', 'days', 'mapping', 'is_override']
    list_filter = ['sprint', 'team', 'is_override']


@admin.register(SprintForecastReviewComplete)
class SprintForecastReviewCompleteAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'completed_at', 'completed_by', 'override_applied']


@admin.register(RechargeDetail)
class RechargeDetailAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team', 'assignee', 'project', 'label', 'type', 'total_days', 'total_cost']
    list_filter = ['sprint', 'type']


class RechargeStoryInline(admin.TabularInline):
    model = RechargeStory
    extra = 0


@admin.register(Recharge)
class RechargeAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'type', 'programme', 'project', 'total_days', 'total_cost']
    list_filter = ['sprint', 'type']
    inlines = [RechargeStoryInline]
