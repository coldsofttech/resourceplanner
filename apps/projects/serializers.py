from rest_framework import serializers

from .models import (
    Project,
    ProjectBudget,
    ProjectBudgetHistory,
    ProjectCode,
    ProjectComment,
    ProjectContact,
    ProjectContactHistory,
    ProjectEstimate,
    ProjectEstimateHistory,
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
    code = serializers.SerializerMethodField()

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

    def get_code(self, obj):
        prefetched = getattr(obj, "_prefetched_codes", None)
        if prefetched is not None:
            return prefetched[0].code if prefetched else None
        entry = obj.codes.order_by("-created_at").first()
        return entry.code if entry else None


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


class ProjectCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCode
        fields = ["id", "code", "notes", "created_at"]
        read_only_fields = ["created_at"]


class ProjectEstimateSerializer(serializers.ModelSerializer):
    version_label = serializers.CharField(read_only=True)
    total_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    tshirt_size = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ProjectEstimate
        fields = [
            "id",
            "project",
            "version",
            "version_label",
            "estimate_link",
            "shared_by",
            "reviewed_by",
            "status",
            "status_display",
            "estimate_days",
            "contingency_pct",
            "day_rate",
            "total_cost",
            "tshirt_size",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "project",
            "version",
            "version_label",
            "day_rate",
            "total_cost",
            "tshirt_size",
            "created_at",
            "updated_at",
        ]


class ProjectEstimateHistorySerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ProjectEstimateHistory
        fields = [
            "id",
            "estimate",
            "action",
            "action_display",
            "previous_status",
            "new_status",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class ProjectBudgetSerializer(serializers.ModelSerializer):
    financial_year_display = serializers.CharField(
        source="financial_year.short_fy", read_only=True
    )
    financial_year_long = serializers.CharField(
        source="financial_year.long_fy", read_only=True
    )
    estimate_version_label = serializers.SerializerMethodField()
    estimate_total_cost = serializers.SerializerMethodField()
    actual_budget = serializers.SerializerMethodField()
    remaining_budget = serializers.SerializerMethodField()
    budget_risk = serializers.SerializerMethodField()
    budget_risk_display = serializers.SerializerMethodField()
    budget_risk_short = serializers.SerializerMethodField()
    budget_risk_pct = serializers.SerializerMethodField()

    class Meta:
        model = ProjectBudget
        fields = [
            "id",
            "project",
            "financial_year",
            "financial_year_display",
            "financial_year_long",
            "allocated_budget",
            "refined_budget",
            "estimate_version",
            "estimate_version_label",
            "notes",
            "actual_budget",
            "estimate_total_cost",
            "remaining_budget",
            "budget_risk",
            "budget_risk_display",
            "budget_risk_short",
            "budget_risk_pct",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "created_at", "updated_at"]

    def get_estimate_version_label(self, obj):
        if obj.estimate_version:
            return obj.estimate_version.version_label
        return None

    def get_estimate_total_cost(self, obj):
        if obj.estimate_version:
            return obj.estimate_version.total_cost
        return None

    def get_actual_budget(self, obj):
        val = getattr(obj, "_actual_budget", obj.actual_budget)
        return val

    def get_remaining_budget(self, obj):
        val = getattr(obj, "_remaining_budget", obj.remaining_budget)
        return val

    def get_budget_risk(self, obj):
        return getattr(obj, "_budget_risk", None)

    def get_budget_risk_display(self, obj):
        return getattr(obj, "_budget_risk_display", "—")

    def get_budget_risk_short(self, obj):
        return getattr(obj, "_budget_risk_short", "—")

    def get_budget_risk_pct(self, obj):
        return getattr(obj, "_budget_risk_pct", "-")


class ProjectBudgetHistorySerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    financial_year_display = serializers.CharField(
        source="financial_year.short_fy", read_only=True
    )
    previous_estimate_label = serializers.SerializerMethodField()
    new_estimate_label = serializers.SerializerMethodField()

    class Meta:
        model = ProjectBudgetHistory
        fields = [
            "id",
            "action",
            "action_display",
            "financial_year",
            "financial_year_display",
            "previous_allocated_budget",
            "previous_refined_budget",
            "previous_estimate_version",
            "previous_estimate_label",
            "previous_total_cost",
            "new_allocated_budget",
            "new_refined_budget",
            "new_estimate_version",
            "new_estimate_label",
            "new_total_cost",
            "notes",
            "created_at",
        ]
        read_only_fields = fields

    def get_previous_estimate_label(self, obj):
        if obj.previous_estimate_version:
            return obj.previous_estimate_version.version_label
        return None

    def get_new_estimate_label(self, obj):
        if obj.new_estimate_version:
            return obj.new_estimate_version.version_label
        return None


class ProjectBudgetLifetimeSerializer(serializers.Serializer):
    total_actual_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    total_estimate_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    budget_risk = serializers.CharField(allow_null=True)
    budget_risk_display = serializers.CharField()
    budget_risk_short = serializers.CharField()
    budget_risk_pct = serializers.CharField()
    partial_budget_warning = serializers.BooleanField()


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


class ProjectContactReadSerializer(serializers.ModelSerializer):
    from apps.contacts.serializers import ContactSerializer

    contact = ContactSerializer(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = ProjectContact
        fields = [
            "id",
            "contact",
            "role",
            "role_display",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ProjectContactWriteSerializer(serializers.Serializer):
    """Handles both contact_id path and name+email path."""

    contact_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=ProjectContact.ROLE_CHOICES)

    def validate(self, data):
        # if not data.get("contact_id"):
        #     if not data.get("name") or not data.get("email"):
        #         raise serializers.ValidationError(
        #             "Provide contact_id or both name and email."
        #         )
        # return data
        contact_id = data.get("contact_id")
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()

        if not contact_id and not (name and email):
            raise serializers.ValidationError(
                "Provide contact_id or both name and email."
            )
        # normalise so service always gets clean values
        data["name"] = name
        data["email"] = email
        return data


class ProjectContactArchiveSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ProjectContactHistorySerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    contact_email = serializers.CharField(source="contact.email", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = ProjectContactHistory
        fields = [
            "id",
            "contact_name",
            "contact_email",
            "role",
            "role_display",
            "action",
            "action_display",
            "reason",
            "created_at",
        ]
