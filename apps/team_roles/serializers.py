from rest_framework import serializers

from .models import TeamRole


class TeamRoleSerializer(serializers.ModelSerializer):
    """
    Serializer for team roles.
    """

    class Meta:
        model = TeamRole
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

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
        fields = ['id', 'role', 'is_active', 'is_assignable', 'is_default']
