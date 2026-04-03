from django.contrib import admin

from .models import OfficeLocation


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ['city', 'country', 'is_active', 'is_default', 'created_at', 'updated_at']
    list_filter = ['is_active', 'is_default', 'country']
    search_fields = ['city', 'country']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['country', 'city']
