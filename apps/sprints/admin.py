from django.contrib import admin

from .models import Sprint


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ['sprint_name', 'financial_year', 'sprint_number', 'start_date', 'end_date', 'month', 'is_active',
                    'is_overridden']
    list_filter = ['financial_year', 'is_active', 'is_overridden', 'month']
    search_fields = ['sprint_name', 'notes']
    readonly_fields = ['month', 'created_at', 'updated_at']
    ordering = ['financial_year', 'sprint_number']
