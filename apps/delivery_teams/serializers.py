from rest_framework import serializers

from .models import DeliveryTeam


class DeliveryTeamSerializer(serializers.ModelSerializer):
    """
    Serializer for delivery teams.
    """
    avatar_svg = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryTeam
        fields = "__all__"
        read_only_fields = ["member_count", "created_at", "updated_at"]

    def get_avatar_svg(self, obj):
        from apps.core.identicon import generate_svg
        return generate_svg(obj.name, size=80)

    def validate_team(self, value):
        name = value
        if len(name) > 120:
            raise serializers.ValidationError(
                "Team name must be 120 characters of fewer."
            )
        return name


class DeliveryTeamExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for delivery teams.
    """

    class Meta:
        model = DeliveryTeam
        fields = ["id", "name", "description", "member_count", "is_active"]
