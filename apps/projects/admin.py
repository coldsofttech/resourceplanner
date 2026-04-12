from django.contrib import admin

from .models import Project, ProjectCollaborator


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
