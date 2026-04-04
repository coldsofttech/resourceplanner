from django.contrib import admin

from .models import FinancialYear


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ['long_fy', 'short_fy', 'start_date', 'end_date', 'span_days', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['long_fy', 'short_fy', 'notes']
    readonly_fields = ['long_fy', 'short_fy', 'span_days', 'created_at', 'updated_at']
    ordering = ['-start_date']
