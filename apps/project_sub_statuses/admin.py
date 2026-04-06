from django.contrib import admin

from .models import ProjectSubStatus


@admin.register(ProjectSubStatus)
class ProjectSubStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'main_status', 'order', 'is_active', 'created_at', 'updated_at']
    list_filter = ['main_status', 'is_active']
    search_fields = ['name', 'main_status']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['main_status', 'order', 'name']
