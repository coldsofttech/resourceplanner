from django.contrib import admin

from .models import TeamRole


@admin.register(TeamRole)
class TeamRoleAdmin(admin.ModelAdmin):
    list_display = ['role', 'is_active', 'is_default', 'is_assignable', 'created_at', 'updated_at']
    list_filter = ['is_active', 'is_default', 'is_assignable']
    search_fields = ['role']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['role']
