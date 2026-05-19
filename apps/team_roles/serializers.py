from rest_framework import serializers

from .models import TeamRole


class TeamRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for team roles.
    """
    total_members = serializers.SerializerMethodField()
    active_members = serializers.SerializerMethodField()
    inactive_members = serializers.SerializerMethodField()

    class Meta:
        model = TeamRole
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_total_members(self, obj):
        return getattr(obj, 'total_members', None)

    def get_active_members(self, obj):
        return getattr(obj, 'active_members', None)

    def get_inactive_members(self, obj):
        return getattr(obj, 'inactive_members', None)

    def validate_role(self, value):
        role = value.strip()
        if not role:
            raise serializers.ValidationError(
                "Role cannot be blank."
            )
        if len(role) > 100:
            raise serializers.ValidationError(
                "Role must be 100 characters or fewer."
            )
        return role


class TeamRoleExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for Team Roles.
    """

    class Meta:
        model = TeamRole
        fields = ['id', 'role', 'is_active', 'is_assignable', 'is_shareable', 'is_default']
