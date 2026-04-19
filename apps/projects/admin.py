from django.contrib import admin

from .models import (
    Project,
    ProjectCollaborator,
    ProjectContact,
    ProjectContactHistory,
    ProjectLink,
)


class ProjectCollaboratorInline(admin.TabularInline):
    model = ProjectCollaborator
    extra = 1
    autocomplete_fields = ["team"]
    verbose_name = "Collaborating team"
    verbose_name_plural = "Collaborating teams"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "project_type",
        "programme",
        "status",
        "sub_status",
        "assigned_team",
        "confidence",
        "priority",
        "is_active",
        "created_at",
        "updated_at",
    ]
    list_filter = [
        "status",
        "confidence",
        "priority",
        "is_active",
        "project_type",
        "programme",
    ]
    search_fields = ["name", "code"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["name"]
    autocomplete_fields = ["project_type", "programme", "sub_status", "assigned_team"]
    inlines = [ProjectCollaboratorInline]


@admin.register(ProjectCollaborator)
class ProjectCollaboratorAdmin(admin.ModelAdmin):
    list_display = ["project", "team", "added_at"]
    list_filter = ["team"]
    search_fields = ["project__name", "team__name"]
    readonly_fields = ["added_at"]
    autocomplete_fields = ["project", "team"]


@admin.register(ProjectContact)
class ProjectContactAdmin(admin.ModelAdmin):
    list_display = ["project", "contact", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["contact__name", "contact__email", "project__name"]
    raw_id_fields = ["project", "contact"]


@admin.register(ProjectContactHistory)
class ProjectContactHistoryAdmin(admin.ModelAdmin):
    list_display = ["contact", "project", "role", "action", "created_at"]
    list_filter = ["role", "action"]
    search_fields = ["contact__name", "project__name"]
    readonly_fields = ["project", "contact", "role", "action", "reason", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProjectLink)
class ProjectLinkAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "url", "updated_at"]
    list_filter = ["project"]
    search_fields = ["title", "url"]
    readonly_fields = ["created_at", "updated_at"]
