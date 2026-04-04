from rest_framework import serializers

from .models import Skill


class SkillSerializer(serializers.ModelSerializer):
    """
    Serializer for skills.
    """
    total_members = serializers.SerializerMethodField()
    active_members = serializers.SerializerMethodField()
    inactive_members = serializers.SerializerMethodField()

    class Meta:
        model = Skill
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_total_members(self, obj):
        return getattr(obj, 'total_members', None)

    def get_active_members(self, obj):
        return getattr(obj, 'active_members', None)

    def get_inactive_members(self, obj):
        return getattr(obj, 'inactive_members', None)

    def validate_skill(self, value):
        code = value.strip().upper()
        if not code.isalnum():
            raise serializers.ValidationError(
                "Skill code must contain only letters and numbers."
            )
        if len(code) > 20:
            raise serializers.ValidationError(
                "Skill code must be 20 characters or fewer."
            )
        return code


class SkillExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for Skills.
    """

    class Meta:
        model = Skill
        fields = ['id', 'skill', 'description', 'is_active']
