from django.contrib import admin

from .models import ProjectType


@admin.register(ProjectType)
class ProjectTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at', 'updated_at']
    list_filter = []
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
