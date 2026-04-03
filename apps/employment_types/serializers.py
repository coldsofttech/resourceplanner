from rest_framework import serializers

from .models import EmploymentType


class EmploymentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer for employment types.
    """

    class Meta:
        model = EmploymentType
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

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
