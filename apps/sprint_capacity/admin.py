from django.contrib import admin

from .models import SprintCapacity


@admin.register(SprintCapacity)
class SprintCapacityAdmin(admin.ModelAdmin):
    list_display = ['sprint', 'team_member', 'working_days', 'holiday_days', 'leave_days', 'net_capacity']
    list_filter = ['sprint__financial_year', 'sprint']
    search_fields = ['team_member__first_name', 'team_member__last_name', 'sprint__sprint_name']
    ordering = ['sprint', 'team_member']
