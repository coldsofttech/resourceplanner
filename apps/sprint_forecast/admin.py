from django.contrib import admin

from .models import (
    ImportReview,
    ImportReviewResult,
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    Recharge,
    RechargeDetail,
    RechargeStory,
    SprintConfirmedRow,
    SprintImport,
    SprintImportReviewComplete,
    SprintImportRow,
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


class SprintImportRowInline(admin.TabularInline):
    model = SprintImportRow
    extra = 0
    fields = ['order', 'story_type', 'jira_id', 'title', 'assignee', 'efforts_ms', 'label', 'mapping', 'is_manually_added']
    readonly_fields = ['order']


@admin.register(SprintImport)
class SprintImportAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team', 'import_type', 'version_number', 'status', 'imported_at', 'imported_by']
    list_filter = ['import_type', 'status', 'sprint', 'team']
    inlines = [SprintImportRowInline]


@admin.register(ImportReview)
class ImportReviewAdmin(admin.ModelAdmin):
    list_display = ['sprint_import', 'reviewed_at', 'reviewed_by']


@admin.register(ImportReviewResult)
class ImportReviewResultAdmin(admin.ModelAdmin):
    list_display = ['review', 'row', 'check_type', 'status', 'message']
    list_filter = ['check_type', 'status']


@admin.register(SprintConfirmedRow)
class SprintConfirmedRowAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team', 'import_type', 'jira_id', 'title', 'assignee', 'days', 'mapping', 'is_override']
    list_filter = ['sprint', 'team', 'import_type', 'is_override']


@admin.register(SprintImportReviewComplete)
class SprintImportReviewCompleteAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'import_type', 'completed_at', 'completed_by', 'override_applied']
    list_filter = ['import_type']


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
