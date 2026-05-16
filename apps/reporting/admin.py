from django.contrib import admin

from .models import DemandCapacityConfig, ProgrammeCategoryMapping, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "report_type", "is_active", "sort_order"]
    list_filter = ["report_type", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]


class ProgrammeCategoryMappingInline(admin.TabularInline):
    model = ProgrammeCategoryMapping
    extra = 0
    autocomplete_fields = ["programme"]
    readonly_fields = ["created_at"]


@admin.register(DemandCapacityConfig)
class DemandCapacityConfigAdmin(admin.ModelAdmin):
    list_display = ["plan", "version", "created_at"]
    inlines = [ProgrammeCategoryMappingInline]
    readonly_fields = ["created_at", "updated_at"]
