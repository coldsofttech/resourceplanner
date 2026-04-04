from django.contrib import admin

from .models import LeaveDay, MemberLeave


@admin.register(MemberLeave)
class MemberLeaveAdmin(admin.ModelAdmin):
    list_display = ['member', 'start_date', 'end_date', 'days', 'is_half_day', 'half_day_period', 'created_at']
    list_filter = ['is_half_day', 'member__location']
    search_fields = ['member__first_name', 'member__last_name', 'note']
    readonly_fields = ['days', 'created_at', 'updated_at']
    ordering = ['start_date', 'member']
    date_hierarchy = 'start_date'


@admin.register(LeaveDay)
class LeaveDayAdmin(admin.ModelAdmin):
    list_display = ['member', 'date', 'leave', 'is_half_day', 'half_day_period']
    list_filter = ['is_half_day', 'member__location']
    search_fields = ['member__first_name', 'member__last_name']
    readonly_fields = ['member', 'leave', 'date', 'is_half_day', 'half_day_period']
    ordering = ['date', 'member']
    date_hierarchy = 'date'
