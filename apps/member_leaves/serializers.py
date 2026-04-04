from rest_framework import serializers

from .models import LeaveDay, MemberLeave


class MemberLeaveSerializer(serializers.ModelSerializer):
    """
    Full serializer — accepts member as PK on write; returns a nested summary on read.
    """
    member = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.team_members.models', fromlist=['TeamMember']).TeamMember.objects.filter(
            is_active=True),
    )
    member_name = serializers.SerializerMethodField(read_only=True)
    member_location = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MemberLeave
        fields = '__all__'
        read_only_fields = ['days', 'created_at', 'updated_at']

    def get_member_name(self, obj):
        return obj.member.display_name
        # return f"{obj.member.first_name} {obj.member.last_name}"

    def get_member_location(self, obj):
        loc = getattr(obj.member, 'location', None)
        if loc is None:
            return None
        return {'id': loc.pk, 'city': loc.city, 'country': loc.country}

    def validate(self, attrs):
        start = attrs.get('start_date') or (self.instance.start_date if self.instance else None)
        end = attrs.get('end_date') or (self.instance.end_date if self.instance else None)
        is_half = attrs.get('is_half_day', getattr(self.instance, 'is_half_day', False))
        period = attrs.get('half_day_period', getattr(self.instance, 'half_day_period', None))

        if start and end and end < start:
            raise serializers.ValidationError("end_date must be on or after start_date.")

        if is_half:
            if start and end and start != end:
                raise serializers.ValidationError(
                    "Half-day leave must have start_date equal to end_date."
                )
            if not period:
                raise serializers.ValidationError(
                    "half_day_period (AM or PM) is required for half-day leaves."
                )
        return attrs


class LeaveDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveDay
        fields = ['id', 'member', 'leave', 'date', 'is_half_day', 'half_day_period']


class MemberLeaveExportSerializer(serializers.ModelSerializer):
    """
    Flat serializer for CSV / PDF export.
    """
    member_name = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = MemberLeave
        fields = ['id', 'member_name', 'location', 'start_date', 'end_date',
                  'is_half_day', 'half_day_period', 'days', 'note']

    def get_member_name(self, obj):
        return obj.member.display_name

    def get_location(self, obj):
        loc = getattr(obj.member, 'location', None)
        if loc is None:
            return ''
        return f"{loc.city}, {loc.country}"
