from django.contrib import admin

from .models import EmploymentType


@admin.register(EmploymentType)
class EmploymentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'is_default', 'created_at', 'updated_at']
    list_filter = ['is_active', 'is_default']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
