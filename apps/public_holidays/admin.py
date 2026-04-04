from django.contrib import admin

from .models import PublicHoliday


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'date', 'created_at', 'updated_at']
    list_filter = ['location']
    search_fields = ['name', 'location__city', 'location__country']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['date', 'location']
    date_hierarchy = 'date'
