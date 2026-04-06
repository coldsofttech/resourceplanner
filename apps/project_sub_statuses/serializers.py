from rest_framework import serializers

from .models import ProjectSubStatus
from .services import ProjectSubStatusService


class ProjectSubStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSubStatus
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        name = value
        if len(name) > 100:
            raise serializers.ValidationError("Project sub status must be 100 characters of fewer.")
        return name

    def validate_main_status(self, value):
        main_status = value
        if main_status.upper() not in ProjectSubStatusService.MAIN_STATUSES:
            raise serializers.ValidationError(f"Invalid main status. Expected {ProjectSubStatusService.MAIN_STATUSES}")
        return main_status


class ProjectSubStatusExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSubStatus
        fields = ['id', 'name', 'main_status', 'order', 'is_active']
