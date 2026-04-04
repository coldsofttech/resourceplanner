from rest_framework import serializers

from .models import TeamMember, TeamMemberHistory
from ..delivery_teams.models import DeliveryTeam
from ..delivery_teams.serializers import DeliveryTeamSerializer
from ..employment_types.models import EmploymentType
from ..employment_types.serializers import EmploymentTypeSerializer
from ..office_locations.models import OfficeLocation
from ..office_locations.serializers import OfficeLocationSerializer
from ..skills.models import Skill
from ..skills.serializers import SkillSerializer
from ..team_roles.models import TeamRole
from ..team_roles.serializers import TeamRoleSerializer


class TeamMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for team members.
    """
    location = serializers.PrimaryKeyRelatedField(
        queryset=OfficeLocation.objects.all()
    )
    employment_type = serializers.PrimaryKeyRelatedField(
        queryset=EmploymentType.objects.all()
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=TeamRole.objects.all()
    )
    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        required=False,
    )
    team = serializers.PrimaryKeyRelatedField(
        queryset=DeliveryTeam.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = TeamMember
        fields = '__all__'
        read_only_fields = ['display_name', 'full_name', 'created_at', 'updated_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        rep["location"] = OfficeLocationSerializer(instance.location).data
        rep["employment_type"] = EmploymentTypeSerializer(instance.employment_type).data
        rep["role"] = TeamRoleSerializer(instance.role).data
        rep["skills"] = SkillSerializer(instance.skills.all(), many=True).data
        rep["team"] = (
            DeliveryTeamSerializer(instance.team).data
            if instance.team else None
        )

        return rep

    def validate_first_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("First name is required")
        if len(name) > 80:
            raise serializers.ValidationError("First name must be less than 80 characters")
        return name

    def validate_last_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Last name is required")
        if len(name) > 80:
            raise serializers.ValidationError("Last name must be less than 80 characters")
        return name

    def validate_email_address(self, value):
        email = value.lower().strip()
        if not email:
            raise serializers.ValidationError("Email address is required")
        if len(email) > 254:
            raise serializers.ValidationError("Email address must be less than 254 characters")
        return email

    def validate_default_holidays(self, value):
        if value < 0:
            raise serializers.ValidationError("Default holidays cannot be negative")
        if value > 365:
            raise serializers.ValidationError("Default holidays cannot be greater than 365")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = attrs.get("end_date") or getattr(self.instance, "end_date", None)

        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError("End date must be greater than start date")

        if not attrs.get("display_name"):
            first_name = attrs.get("first_name", "").strip()
            last_name = attrs.get("last_name", "").strip()
            attrs["display_name"] = f"{last_name}, {first_name}"

        return attrs


class TeamMemberHistorySerializer(serializers.ModelSerializer):
    """
    Team history serializer.
    """
    from_team = DeliveryTeamSerializer()
    to_team = DeliveryTeamSerializer()

    class Meta:
        model = TeamMemberHistory
        fields = ['id', 'from_team', 'to_team', 'moved_on', 'note']


class MoveTeamSerializer(serializers.ModelSerializer):
    """
    Move team-specific serializer for team members.
    """

    class Meta:
        model = TeamMemberHistory
        fields = ['from_team', 'to_team', 'note']


class TeamMemberExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for team members.
    """
    location = serializers.PrimaryKeyRelatedField(
        queryset=OfficeLocation.objects.all()
    )
    employment_type = serializers.PrimaryKeyRelatedField(
        queryset=EmploymentType.objects.all()
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=TeamRole.objects.all()
    )
    skills = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        required=False,
    )
    team = serializers.PrimaryKeyRelatedField(
        queryset=DeliveryTeam.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = TeamMember
        fields = [
            'id', 'first_name', 'last_name', 'display_name', 'email_address', 'skills',
            'location', 'employment_type', 'role', 'team', 'start_date', 'end_date',
            'default_holidays', 'is_active',
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        location = OfficeLocationSerializer(instance.location).data
        rep["location"] = f"{location.get('city')}, {location.get('country')}"
        rep["employment_type"] = EmploymentTypeSerializer(instance.employment_type).data.get('name')
        rep["role"] = TeamRoleSerializer(instance.role).data.get('role')
        skills = SkillSerializer(instance.skills.all(), many=True).data
        rep["skills"] = ", ".join(s["skill"] for s in skills) if skills else ""
        team = DeliveryTeamSerializer(instance.team).data
        rep["team"] = team.get('name') if team else None

        return rep
