from rest_framework import serializers

from .models import DemandCapacityConfig, ProgrammeCategoryMapping, Report


class ReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "report_type",
            "is_active",
            "sort_order",
            "created_at",
            "created_by",
            "created_by_name",
            "updated_at",
            "updated_by",
            "updated_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return obj.updated_by.get_full_name() or obj.updated_by.username
        return None


class CustomReportCreateSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=100)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    sort_order = serializers.IntegerField(required=False, default=0)

    def validate_slug(self, value):
        if Report.objects.filter(slug=value).exists():
            raise serializers.ValidationError("A report with this slug already exists.")
        return value


class DemandCapacityConfigSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    version_number = serializers.IntegerField(source="version.version", read_only=True)
    version_status = serializers.CharField(source="version.status", read_only=True)

    class Meta:
        model = DemandCapacityConfig
        fields = [
            "id",
            "plan",
            "plan_name",
            "version",
            "version_number",
            "version_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProgrammeCategoryMappingSerializer(serializers.ModelSerializer):
    programme_name = serializers.CharField(source="programme.name", read_only=True)

    class Meta:
        model = ProgrammeCategoryMapping
        fields = [
            "id",
            "config",
            "programme",
            "programme_name",
            "category_label",
            "created_at",
        ]
        read_only_fields = ["id", "config", "created_at"]


class MappingUpsertSerializer(serializers.Serializer):
    programme_id = serializers.IntegerField()
    # Allow blank: empty string means "delete this mapping"
    category_label = serializers.CharField(max_length=200, allow_blank=True, default="")


class BulkMappingUpsertSerializer(serializers.Serializer):
    mappings = MappingUpsertSerializer(many=True)

    def validate_mappings(self, value):
        if not value:
            raise serializers.ValidationError("At least one mapping entry is required.")
        return value
