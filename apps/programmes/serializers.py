from rest_framework import serializers

from .services import PROTECTED_PROGRAMME_NAME
from .models import Programme


class ProgrammeSerializer(serializers.ModelSerializer):
    is_protected = serializers.SerializerMethodField()

    class Meta:
        model = Programme
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def get_is_protected(self, obj):
        return obj.name == PROTECTED_PROGRAMME_NAME

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required and cannot be blank.")
        if len(value.strip()) > 100:
            raise serializers.ValidationError("Name must be 100 characters or fewer.")
        return value.strip()

    def validate_description(self, value):
        if value:
            return value.strip() or None
        return None


class ProjectBudgetSummarySerializer(serializers.Serializer):
    actual_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    estimated_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    remaining_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    risk_pct = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    risk_display = serializers.CharField(allow_null=True)
    risk_short = serializers.CharField(allow_null=True)
    risk = serializers.CharField(allow_null=True)


class ProjectSummaryRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    status = serializers.CharField()
    financial_year = serializers.CharField(allow_null=True)
    assigned_team = serializers.CharField(allow_null=True)
    actual_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    estimate_total_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    remaining_budget = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    risk_pct = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    risk = serializers.CharField(allow_null=True)
    risk_display = serializers.CharField(allow_null=True)
    risk_short = serializers.CharField(allow_null=True)


class ProgrammeSummarySerializer(serializers.Serializer):
    total_count = serializers.IntegerField()
    total_pages = serializers.IntegerField()
    current_page = serializers.IntegerField()
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()
    page_size = serializers.IntegerField()
    results = ProjectSummaryRowSerializer(many=True)
    summary = ProjectBudgetSummarySerializer()


class ProgrammeExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Programme
        fields = ["id", "name", "description", "is_active"]
