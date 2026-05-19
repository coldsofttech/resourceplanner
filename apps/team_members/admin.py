from django.contrib import admin

from .models import TeamMember, TeamMemberAssignment, TeamMemberHistory


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'email_address', 'location', 'employment_type', 'role',
        'start_date', 'end_date', 'default_holidays', 'is_active', 'created_at', 'updated_at',
    ]
    list_filter = ['is_active', 'location', 'employment_type', 'role']
    search_fields = [
        'first_name', 'last_name', 'email_address', 'display_name',
        'user__email', 'user__first_name', 'user__last_name',
    ]
    readonly_fields = ['display_name', 'created_at', 'updated_at']
    ordering = ['display_name']


@admin.register(TeamMemberAssignment)
class TeamMemberAssignmentAdmin(admin.ModelAdmin):
    list_display = ['member', 'team']
    list_filter = ['team']
    search_fields = [
        'member__first_name', 'member__last_name', 'member__email_address',
        'team__name',
    ]
    raw_id_fields = ['member']


@admin.register(TeamMemberHistory)
class TeamMemberHistoryAdmin(admin.ModelAdmin):
    list_display = ['member', 'from_team', 'to_team', 'moved_on', 'note', 'created_at']
    list_filter = ['to_team', 'from_team']
    search_fields = [
        'member__first_name', 'member__last_name', 'member__email_address',
        'member__user__email', 'note',
    ]
    readonly_fields = ['created_at']
    ordering = ['-moved_on']
