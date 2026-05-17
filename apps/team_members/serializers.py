from django.contrib.auth import get_user_model
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

User = get_user_model()


class TeamMemberSerializer(serializers.ModelSerializer):
    location = serializers.PrimaryKeyRelatedField(queryset=OfficeLocation.objects.all())
    employment_type = serializers.PrimaryKeyRelatedField(queryset=EmploymentType.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=TeamRole.objects.all())
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
    # name/email are optional at field level — required logic lives in validate()
    first_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    email_address = serializers.CharField(max_length=254, required=False, allow_blank=True)

    class Meta:
        model = TeamMember
        fields = '__all__'
        read_only_fields = ['display_name', 'full_name', 'created_at', 'updated_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        rep['location'] = OfficeLocationSerializer(instance.location).data
        rep['employment_type'] = EmploymentTypeSerializer(instance.employment_type).data
        rep['role'] = TeamRoleSerializer(instance.role).data
        rep['skills'] = SkillSerializer(instance.skills.all(), many=True).data
        rep['team'] = DeliveryTeamSerializer(instance.team).data if instance.team else None

        if instance.user_id:
            user = instance.user
            rep['first_name'] = user.first_name
            rep['last_name'] = user.last_name
            rep['email_address'] = user.email
            rep['user'] = {
                'id': user.pk,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        else:
            rep['user'] = None

        return rep

    def validate_user(self, value):
        if value:
            try:
                existing = value.team_member
                if self.instance is None or existing.pk != self.instance.pk:
                    raise serializers.ValidationError(
                        "This user already has a team member profile."
                    )
            except TeamMember.DoesNotExist:
                pass
        return value

    def validate_default_holidays(self, value):
        if value < 0:
            raise serializers.ValidationError("Default holidays cannot be negative.")
        if value > 365:
            raise serializers.ValidationError("Default holidays cannot exceed 365.")
        return value

    def validate(self, attrs):
        user = attrs.get('user')

        if user:
            # Populate stored fields from the linked user account.
            attrs['first_name'] = user.first_name
            attrs['last_name'] = user.last_name
            attrs['email_address'] = user.email
        elif self.instance is None:
            # Create without a user: all three name/email fields are required.
            errors = {}
            fn = (attrs.get('first_name') or '').strip()
            ln = (attrs.get('last_name') or '').strip()
            em = (attrs.get('email_address') or '').strip()
            if not fn:
                errors['first_name'] = 'First name is required.'
            if not ln:
                errors['last_name'] = 'Last name is required.'
            if not em:
                errors['email_address'] = 'Email address is required.'
            if errors:
                raise serializers.ValidationError(errors)
            attrs['first_name'] = fn
            attrs['last_name'] = ln
            attrs['email_address'] = em.lower()
        else:
            # Partial update: clean whatever was submitted.
            if 'first_name' in attrs:
                fn = attrs['first_name'].strip()
                if not fn:
                    raise serializers.ValidationError({'first_name': 'First name cannot be blank.'})
                if len(fn) > 80:
                    raise serializers.ValidationError({'first_name': 'First name must be at most 80 characters.'})
                attrs['first_name'] = fn
            if 'last_name' in attrs:
                ln = attrs['last_name'].strip()
                if not ln:
                    raise serializers.ValidationError({'last_name': 'Last name cannot be blank.'})
                if len(ln) > 80:
                    raise serializers.ValidationError({'last_name': 'Last name must be at most 80 characters.'})
                attrs['last_name'] = ln
            if 'email_address' in attrs:
                em = attrs['email_address'].strip().lower()
                if not em:
                    raise serializers.ValidationError({'email_address': 'Email address cannot be blank.'})
                if len(em) > 254:
                    raise serializers.ValidationError({'email_address': 'Email must be at most 254 characters.'})
                attrs['email_address'] = em

        start_date = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        end_date = attrs.get('end_date') or getattr(self.instance, 'end_date', None)
        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError('End date must be greater than or equal to start date.')

        if not attrs.get('display_name'):
            first = (attrs.get('first_name') or getattr(self.instance, 'first_name', '') or '').strip()
            last = (attrs.get('last_name') or getattr(self.instance, 'last_name', '') or '').strip()
            if first or last:
                attrs['display_name'] = f"{last}, {first}" if last and first else last or first

        return attrs


class TeamMemberHistorySerializer(serializers.ModelSerializer):
    from_team = DeliveryTeamSerializer()
    to_team = DeliveryTeamSerializer()

    class Meta:
        model = TeamMemberHistory
        fields = ['id', 'from_team', 'to_team', 'moved_on', 'note']


class MoveTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamMemberHistory
        fields = ['from_team', 'to_team', 'note']


class TeamMemberExportSerializer(serializers.ModelSerializer):
    location = serializers.PrimaryKeyRelatedField(queryset=OfficeLocation.objects.all())
    employment_type = serializers.PrimaryKeyRelatedField(queryset=EmploymentType.objects.all())
    role = serializers.PrimaryKeyRelatedField(queryset=TeamRole.objects.all())
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

        if instance.user_id:
            user = instance.user
            rep['first_name'] = user.first_name
            rep['last_name'] = user.last_name
            rep['email_address'] = user.email

        location = OfficeLocationSerializer(instance.location).data
        rep['location'] = f"{location.get('city')}, {location.get('country')}"
        rep['employment_type'] = EmploymentTypeSerializer(instance.employment_type).data.get('name')
        rep['role'] = TeamRoleSerializer(instance.role).data.get('role')
        skills = SkillSerializer(instance.skills.all(), many=True).data
        rep['skills'] = ', '.join(s['skill'] for s in skills) if skills else ''
        team = DeliveryTeamSerializer(instance.team).data if instance.team else None
        rep['team'] = team.get('name') if team else None

        return rep
