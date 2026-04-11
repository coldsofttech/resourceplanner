from rest_framework import serializers

from .models import (
    Project,
    ProjectCollaborator,
    ProjectComment,
    ProjectLabel,
    ProjectStatusHistory,
    ProjectTag,
)


class ProjectSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    project_type_name = serializers.SerializerMethodField()
    programme_name = serializers.SerializerMethodField()
    sub_status_name = serializers.SerializerMethodField()
    assigned_team_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    confidence_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "display_name",
            "project_type",
            "project_type_name",
            "programme",
            "programme_name",
            "code",
            "status",
            "status_display",
            "sub_status",
            "sub_status_name",
            "assigned_team",
            "assigned_team_name",
            "confidence",
            "confidence_display",
            "priority",
            "priority_display",
            "tentative_start_date",
            "tentative_end_date",
            "is_active",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["display_name", "created_at", "updated_at"]

    def get_display_name(self, obj):
        return obj.display_name

    def get_project_type_name(self, obj):
        return obj.project_type.name if obj.project_type_id else None

    def get_programme_name(self, obj):
        return obj.programme.name if obj.programme_id else None

    def get_sub_status_name(self, obj):
        return obj.sub_status.name if obj.sub_status_id else None

    def get_assigned_team_name(self, obj):
        return obj.assigned_team.name if obj.assigned_team_id else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_confidence_display(self, obj):
        return obj.get_confidence_display() if obj.confidence else None

    def get_priority_display(self, obj):
        return obj.get_priority_display() if obj.priority else None

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required and cannot be blank.")
        if len(value.strip()) > 200:
            raise serializers.ValidationError("Name must be 200 characters or fewer.")
        return value.strip()

    def validate_code(self, value):
        if value:
            return value.strip()
        return ""

    def get_tags(self, obj):
        return [
            {"id": pt.tag_id, "name": pt.tag.name}
            for pt in obj.project_tags.select_related("tag").all()
        ]


class ProjectOperationalSerializer(ProjectSerializer):
    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + [
            "efforts_issued",
            "effort_issue_commitment_date",
            "run_cost_applies",
        ]


class ProjectTeamsSerializer(ProjectSerializer):
    assigned_team_name = serializers.SerializerMethodField()
    collaborators = serializers.SerializerMethodField()

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + [
            "assigned_team",
            "assigned_team_name",
            "collaborators",
        ]

    def get_assigned_team_name(self, obj):
        return obj.assigned_team.name if obj.assigned_team_id else None

    def get_collaborators(self, obj):
        return [
            {"id": pc.team_id, "name": pc.team.name}
            for pc in obj.project_collaborators.select_related("team").all()
        ]


class ProjectLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLabel
        fields = "__all__"
        read_only_fields = ["project", "created_at"]


class ProjectLabelSuggestSerializer(serializers.Serializer):
    suggestion = serializers.CharField()


class ProjectStatusHistorySerializer(serializers.ModelSerializer):
    previous_sub_status_name = serializers.SerializerMethodField()
    previous_status_display = serializers.SerializerMethodField()
    new_sub_status_name = serializers.SerializerMethodField()
    new_status_display = serializers.SerializerMethodField()

    class Meta:
        model = ProjectStatusHistory
        fields = [
            "id",
            "project",
            "previous_status",
            "previous_status_display",
            "new_status",
            "new_status_display",
            "previous_sub_status",
            "previous_sub_status_name",
            "new_sub_status",
            "new_sub_status_name",
            "reason",
            "created_at",
        ]
        read_only_fields = fields

    def get_previous_sub_status_name(self, obj):
        return obj.previous_sub_status.name if obj.previous_sub_status else None

    def get_new_sub_status_name(self, obj):
        return obj.new_sub_status.name if obj.new_sub_status else None

    def get_previous_status_display(self, obj):
        if not obj.previous_status:
            return None
        choices = dict(Project.STATUS_CHOICES)
        return choices.get(obj.previous_status, obj.previous_status)

    def get_new_status_display(self, obj):
        if not obj.new_status:
            return None
        choices = dict(Project.STATUS_CHOICES)
        return choices.get(obj.new_status, obj.new_status)


class ProjectTagSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="tag.id", read_only=True)
    name = serializers.CharField(source="tag.name", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ProjectTag
        fields = ["id", "name", "created_at"]


class ProjectCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectComment
        fields = [
            "id",
            "comment",
            "posted_by",
            "is_edited",
            "is_pinned",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "posted_by", "is_edited", "created_at", "updated_at"]


class ProjectExportSerializer(serializers.ModelSerializer):
    project_type_name = serializers.SerializerMethodField()
    programme_name = serializers.SerializerMethodField()
    sub_status_name = serializers.SerializerMethodField()
    assigned_team_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    confidence_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "project_type_name",
            "programme_name",
            "code",
            "status_display",
            "sub_status_name",
            "assigned_team_name",
            "confidence_display",
            "priority_display",
            "tentative_start_date",
            "tentative_end_date",
            "is_active",
        ]

    def get_project_type_name(self, obj):
        return obj.project_type.name if obj.project_type_id else None

    def get_programme_name(self, obj):
        return obj.programme.name if obj.programme_id else None

    def get_sub_status_name(self, obj):
        return obj.sub_status.name if obj.sub_status_id else None

    def get_assigned_team_name(self, obj):
        return obj.assigned_team.name if obj.assigned_team_id else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_confidence_display(self, obj):
        return obj.get_confidence_display() if obj.confidence else None

    def get_priority_display(self, obj):
        return obj.get_priority_display() if obj.priority else None
