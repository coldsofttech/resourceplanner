from rest_framework import serializers

from .models import SprintCapacity


class SprintCapacitySerializer(serializers.ModelSerializer):
    sprint_name = serializers.CharField(source='sprint.sprint_name', read_only=True)
    sprint_number = serializers.IntegerField(source='sprint.sprint_number', read_only=True)
    sprint_start = serializers.DateField(source='sprint.start_date', read_only=True)
    sprint_end = serializers.DateField(source='sprint.end_date', read_only=True)
    fy_label = serializers.CharField(source='sprint.financial_year.long_fy', read_only=True)
    member_name = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = SprintCapacity
        fields = [
            'id',
            'sprint',
            'sprint_name',
            'sprint_number',
            'sprint_start',
            'sprint_end',
            'fy_label',
            'team_member',
            'member_name',
            'team_name',
            'location_name',
            'working_days',
            'holiday_days',
            'leave_days',
            'net_capacity',
        ]
        read_only_fields = fields

    def get_member_name(self, obj) -> str:
        m = obj.team_member
        return f"{m.first_name} {m.last_name}".strip()

    def get_team_name(self, obj) -> str:
        team = obj.team_member.team  # uses prefetch cache when available
        return team.name if team else ''

    def get_location_name(self, obj) -> str:
        loc = getattr(obj.team_member, 'location', None)
        return str(loc) if loc else ''
