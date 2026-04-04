from rest_framework import serializers

from .models import EmploymentType


class EmploymentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for employment types.
    """
    total_members = serializers.SerializerMethodField()
    active_members = serializers.SerializerMethodField()
    inactive_members = serializers.SerializerMethodField()

    class Meta:
        model = EmploymentType
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_total_members(self, obj):
        return getattr(obj, 'total_members', None)

    def get_active_members(self, obj):
        return getattr(obj, 'active_members', None)

    def get_inactive_members(self, obj):
        return getattr(obj, 'inactive_members', None)

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError(
                "Employment type name cannot be blank."
            )
        if len(name) > 100:
            raise serializers.ValidationError(
                "Employment type name must be 100 characters or fewer."
            )
        return name


class EmploymentTypeExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for Employment Types.
    """

    class Meta:
        model = EmploymentType
        fields = ['id', 'name', 'is_active', 'is_default']
