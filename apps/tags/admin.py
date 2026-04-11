from django.contrib import admin

from .models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    list_filter = []
    search_fields = ["name"]
    readonly_fields = ["created_at"]
    ordering = ["name"]
