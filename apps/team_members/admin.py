from django.contrib import admin

from .models import TeamMember, TeamMemberHistory


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = [
        'first_name', 'last_name', 'display_name', 'email_address',
        'location', 'employment_type', 'role', 'team', 'start_date', 'end_date',
        'default_holidays', 'is_active', 'created_at', 'updated_at'
    ]
    list_filter = ['is_active', 'location', 'employment_type', 'role', 'team']
    search_fields = ['first_name', 'last_name', 'email_address']
    readonly_fields = ['display_name', 'created_at', 'updated_at']
    ordering = ['last_name', 'first_name']


@admin.register(TeamMemberHistory)
class TeamMemberHistoryAdmin(admin.ModelAdmin):
    last_display = ['member', 'from_team', 'to_team', 'moved_on', 'note', 'created_at']
    list_filter = ['to_team', 'from_team']
    search_fields = ['member__first_name', 'member__last_name', 'member__email_address', 'note']
    readonly_fields = ['created_at']
    ordering = ['-moved_on']
