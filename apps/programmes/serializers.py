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


class ProgrammeExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Programme
        fields = ["id", "name", "description", "is_active"]
