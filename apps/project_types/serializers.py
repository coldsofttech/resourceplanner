from rest_framework import serializers

from .models import ProjectType


class ProjectTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectType
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_type(self, value):
        name = value
        if len(name) > 60:
            raise serializers.ValidationError(
                "Project type must be 60 characters of fewer."
            )
        return name


class ProjectTypeExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectType
        fields = ['id', 'name', 'description', 'is_active']
