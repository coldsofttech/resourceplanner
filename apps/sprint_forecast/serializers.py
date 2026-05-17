from rest_framework import serializers

from .models import (
    ImportReview,
    ImportReviewResult,
    ProjectActuals,
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    ProjectSprintActual,
    Recharge,
    RechargeDetail,
    RechargeStory,
    RISK_NEUTRAL,
    RISK_WARNING,
    RISK_RISK,
    SprintConfirmedRow,
    SprintImport,
    SprintImportReviewComplete,
    SprintImportRow,
)


class ProjectFinanceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFinanceType
        fields = ['id', 'code', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProjectFinanceTypeMappingSerializer(serializers.ModelSerializer):
    project_type_name = serializers.CharField(source='project_type.name', read_only=True)
    finance_type_code = serializers.CharField(source='finance_type.code', read_only=True)
    finance_type_name = serializers.CharField(source='finance_type.name', read_only=True)

    class Meta:
        model = ProjectFinanceTypeMapping
        fields = [
            'id', 'project_type', 'project_type_name',
            'finance_type', 'finance_type_code', 'finance_type_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ImportReviewResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportReviewResult
        fields = ['id', 'row', 'check_type', 'status', 'message']


class ImportReviewSerializer(serializers.ModelSerializer):
    results = ImportReviewResultSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ImportReview
        fields = ['id', 'sprint_import', 'reviewed_at', 'reviewed_by', 'reviewed_by_name', 'results']

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class SprintImportRowSerializer(serializers.ModelSerializer):
    days = serializers.SerializerMethodField()
    effective_story_type = serializers.CharField(read_only=True)
    effective_jira_id = serializers.CharField(read_only=True)
    effective_title = serializers.CharField(read_only=True)
    effective_assignee_raw = serializers.CharField(read_only=True)
    effective_assignee_id = serializers.SerializerMethodField()
    effective_assignee_name = serializers.SerializerMethodField()
    effective_efforts_ms = serializers.IntegerField(read_only=True)
    effective_sprint_name = serializers.CharField(read_only=True)
    effective_label_id = serializers.SerializerMethodField()
    effective_label_name = serializers.SerializerMethodField()
    effective_mapping_id = serializers.SerializerMethodField()
    effective_mapping_code = serializers.SerializerMethodField()
    has_overrides = serializers.BooleanField(read_only=True)
    latest_review_results = serializers.SerializerMethodField()

    class Meta:
        model = SprintImportRow
        fields = [
            'id', 'sprint_import', 'order', 'is_manually_added',
            'story_type', 'jira_id', 'title', 'assignee_raw', 'assignee',
            'efforts_ms', 'sprint_name', 'label_raw', 'label', 'mapping_raw', 'mapping',
            'story_type_override', 'jira_id_override', 'title_override',
            'assignee_raw_override', 'assignee_override',
            'efforts_ms_override', 'sprint_name_override',
            'label_override', 'mapping_override',
            'days',
            'effective_story_type', 'effective_jira_id', 'effective_title',
            'effective_assignee_raw', 'effective_assignee_id', 'effective_assignee_name',
            'effective_efforts_ms', 'effective_sprint_name',
            'effective_label_id', 'effective_label_name',
            'effective_mapping_id', 'effective_mapping_code',
            'has_overrides', 'latest_review_results',
        ]

    def get_days(self, obj):
        return str(obj.compute_days())

    def get_effective_assignee_id(self, obj):
        a = obj.effective_assignee
        return a.id if a else None

    def get_effective_assignee_name(self, obj):
        a = obj.effective_assignee
        return a.display_name if a else obj.effective_assignee_raw

    def get_effective_label_id(self, obj):
        lbl = obj.effective_label
        return lbl.id if lbl else None

    def get_effective_label_name(self, obj):
        lbl = obj.effective_label
        return lbl.label if lbl else (obj.label_override if obj.label_override else obj.label_raw)

    def get_effective_mapping_id(self, obj):
        m = obj.effective_mapping
        return m.id if m else None

    def get_effective_mapping_code(self, obj):
        m = obj.effective_mapping
        return m.code if m else (obj.mapping_override.code if obj.mapping_override else obj.mapping_raw)

    def get_latest_review_results(self, obj):
        results = list(obj.review_results.order_by('-review__reviewed_at')[:3])
        return ImportReviewResultSerializer(results, many=True).data


class SprintImportSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    imported_by_name = serializers.SerializerMethodField()
    row_count = serializers.SerializerMethodField()
    latest_review = serializers.SerializerMethodField()

    class Meta:
        model = SprintImport
        fields = [
            'id', 'sprint', 'team', 'team_name', 'import_type', 'version_number',
            'status', 'imported_at', 'imported_by', 'imported_by_name',
            'row_count', 'latest_review',
        ]
        read_only_fields = ['id', 'version_number', 'imported_at', 'imported_by']

    def get_imported_by_name(self, obj):
        if obj.imported_by:
            return obj.imported_by.get_full_name() or obj.imported_by.username
        return None

    def get_row_count(self, obj):
        return obj.rows.count()

    def get_latest_review(self, obj):
        review = obj.reviews.order_by('-reviewed_at').first()
        if not review:
            return None
        error_count = review.results.filter(status='error').count()
        pass_count = review.results.filter(status='pass').count()
        return {
            'id': review.id,
            'reviewed_at': review.reviewed_at,
            'error_count': error_count,
            'pass_count': pass_count,
        }


class SprintConfirmedRowSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.display_name', read_only=True)
    label_name = serializers.CharField(source='label.label', read_only=True)
    mapping_code = serializers.CharField(source='mapping.code', read_only=True)

    class Meta:
        model = SprintConfirmedRow
        fields = [
            'id', 'sprint', 'team', 'sprint_import', 'import_type',
            'story_type', 'jira_id', 'title',
            'assignee', 'assignee_name', 'assignee_raw',
            'efforts_ms', 'days', 'sprint_name',
            'label', 'label_name', 'label_raw',
            'mapping', 'mapping_code', 'mapping_raw',
            'is_override',
        ]


class RechargeDetailSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source='assignee.display_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    label_name = serializers.CharField(source='label.label', read_only=True)
    sprint_name = serializers.CharField(source='sprint.sprint_name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)

    class Meta:
        model = RechargeDetail
        fields = [
            'id', 'sprint', 'sprint_name', 'team', 'team_name',
            'assignee', 'assignee_name',
            'programme', 'programme_name',
            'project', 'project_name',
            'label', 'label_name',
            'type', 'total_days', 'total_cost',
            'sprint_import', 'created_at', 'updated_at',
        ]


class RechargeStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargeStory
        fields = ['id', 'recharge', 'jira_id', 'title', 'total_days']


class RechargeSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    sprint_name = serializers.CharField(source='sprint.sprint_name', read_only=True)
    stories = RechargeStorySerializer(many=True, read_only=True)
    finance_contact_emails = serializers.SerializerMethodField()
    project_contact_emails = serializers.SerializerMethodField()

    class Meta:
        model = Recharge
        fields = [
            'id', 'sprint', 'sprint_name', 'type',
            'programme', 'programme_name',
            'project', 'project_name',
            'total_days', 'total_cost',
            'finance_contacts', 'project_contacts',
            'finance_contact_emails', 'project_contact_emails',
            'stories', 'created_at', 'updated_at',
        ]

    def get_finance_contact_emails(self, obj):
        return list(obj.finance_contacts.select_related('contact').values_list('contact__email', flat=True))

    def get_project_contact_emails(self, obj):
        return list(obj.project_contacts.select_related('contact').values_list('contact__email', flat=True))


class SprintImportReviewCompleteSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SprintImportReviewComplete
        fields = [
            'id', 'sprint', 'import_type', 'completed_at', 'completed_by', 'completed_by_name',
            'override_applied', 'override_notes',
        ]

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.username
        return None


class ProjectSprintActualSerializer(serializers.ModelSerializer):
    sprint_name = serializers.CharField(source='sprint.sprint_name', read_only=True)
    sprint_number = serializers.IntegerField(source='sprint.sprint_number', read_only=True)
    sprint_fy_id = serializers.IntegerField(source='sprint.financial_year_id', read_only=True)
    sprint_fy_short = serializers.CharField(source='sprint.financial_year.short_fy', read_only=True)

    class Meta:
        model = ProjectSprintActual
        fields = ['id', 'sprint', 'sprint_name', 'sprint_number', 'sprint_fy_id', 'sprint_fy_short', 'total_cost', 'total_days']


class ProjectActualsSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    programme_name = serializers.CharField(source='programme.name', read_only=True)
    label_name = serializers.CharField(source='label.label', read_only=True)
    all_labels = serializers.SerializerMethodField()
    assigned_team_name = serializers.CharField(source='assigned_team.name', read_only=True)
    collaborator_names = serializers.SerializerMethodField()
    sprint_actuals = ProjectSprintActualSerializer(many=True, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    risk = serializers.CharField(read_only=True)
    last_updated_sprint_name = serializers.CharField(source='last_updated_sprint.sprint_name', read_only=True)

    class Meta:
        model = ProjectActuals
        fields = [
            'id', 'project', 'project_name',
            'programme', 'programme_name',
            'label', 'label_name', 'all_labels',
            'code',
            'assigned_team', 'assigned_team_name',
            'collaborators', 'collaborator_names',
            'estimate_value', 'estimate_value_with_contingency',
            'sprint_actuals',
            'total_cost_till_date',
            'remaining_amount',
            'risk',
            'last_updated_sprint', 'last_updated_sprint_name',
            'created_at', 'updated_at',
        ]

    def get_all_labels(self, obj):
        if not obj.project_id:
            return []
        return list(obj.project.labels.values('id', 'label', 'is_primary').order_by('-is_primary', 'label'))

    def get_collaborator_names(self, obj):
        return list(obj.collaborators.values_list('name', flat=True))
