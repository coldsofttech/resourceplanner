from django.contrib import admin

from .models import DeliveryTeam


@admin.register(DeliveryTeam)
class DeliveryTeamAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]
