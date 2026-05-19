from rest_framework import serializers

from .models import (
    Win, WinEntry,
    MonthlyWin, MonthlyWinSurvey, MonthlyWinSurveyNomination, MonthlyWinResult,
    TeamProductOwner,
)


# ── Weekly Wins ───────────────────────────────────────────────────────────────

class WinEntrySerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WinEntry
        fields = [
            'id', 'win', 'team', 'team_name',
            'title', 'description',
            'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'team_name', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class WinSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()
    team_count = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Win
        fields = [
            'id', 'week_number', 'week_start_date', 'week_end_date',
            'label', 'status', 'reviewed_at', 'reviewed_by_name',
            'entry_count', 'team_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'week_number', 'week_end_date',
            'entry_count', 'team_count', 'label',
            'status', 'reviewed_at', 'reviewed_by_name',
            'created_at',
        ]

    def get_entry_count(self, obj):
        return obj.entries.count()

    def get_team_count(self, obj):
        return obj.entries.values('team').distinct().count()

    def get_label(self, obj):
        return (
            f'Week {obj.week_number} '
            f'({obj.week_start_date.strftime("%d %b %Y")} – {obj.week_end_date.strftime("%d %b %Y")})'
        )

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.email
        return None


class WinDetailSerializer(WinSerializer):
    entries = WinEntrySerializer(many=True, read_only=True)

    class Meta(WinSerializer.Meta):
        fields = WinSerializer.Meta.fields + ['entries']


# ── Monthly Wins ──────────────────────────────────────────────────────────────

class TeamProductOwnerSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)

    class Meta:
        model = TeamProductOwner
        fields = ['id', 'team', 'team_name', 'user', 'user_name', 'user_email', 'is_active', 'created_at']
        read_only_fields = ['id', 'team_name', 'user_name', 'user_email', 'created_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class MonthlyWinNominationSerializer(serializers.ModelSerializer):
    entry_title = serializers.CharField(source='entry.title', read_only=True)
    entry_team_name = serializers.CharField(source='entry.team.name', read_only=True)
    entry_week_number = serializers.IntegerField(source='entry.win.week_number', read_only=True)

    class Meta:
        model = MonthlyWinSurveyNomination
        fields = [
            'id', 'survey', 'entry', 'entry_title', 'entry_team_name', 'entry_week_number',
            'category', 'is_dismissed', 'dismissed_reason', 'nominated_at',
        ]
        read_only_fields = ['id', 'entry_title', 'entry_team_name', 'entry_week_number', 'nominated_at']


class MonthlyWinSurveySerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()
    recipient_email = serializers.EmailField(source='recipient.email', read_only=True)
    team_names = serializers.SerializerMethodField()
    nomination_count = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyWinSurvey
        fields = [
            'id', 'monthly_win', 'phase', 'recipient', 'recipient_name', 'recipient_email',
            'team_names', 'token', 'status', 'sent_at', 'reminder_count', 'last_reminder_at',
            'completed_at', 'nomination_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'recipient_name', 'recipient_email', 'team_names',
            'token', 'sent_at', 'reminder_count', 'last_reminder_at',
            'completed_at', 'nomination_count', 'created_at',
        ]

    def get_recipient_name(self, obj):
        return obj.recipient.get_full_name() or obj.recipient.email

    def get_team_names(self, obj):
        return list(obj.teams.values_list('name', flat=True))

    def get_nomination_count(self, obj):
        return obj.nominations.filter(is_dismissed=False).count()


class MonthlyWinResultSerializer(serializers.ModelSerializer):
    entry_title = serializers.CharField(source='entry.title', read_only=True)
    entry_team_name = serializers.CharField(source='entry.team.name', read_only=True)
    entry_week_number = serializers.IntegerField(source='entry.win.week_number', read_only=True)
    entry_description = serializers.CharField(source='entry.description', read_only=True)

    class Meta:
        model = MonthlyWinResult
        fields = [
            'id', 'monthly_win', 'entry', 'entry_title', 'entry_team_name',
            'entry_week_number', 'entry_description', 'category', 'rank', 'vote_count',
        ]
        read_only_fields = [
            'id', 'entry_title', 'entry_team_name', 'entry_week_number', 'entry_description',
        ]


class MonthlyWinSerializer(serializers.ModelSerializer):
    week_count = serializers.SerializerMethodField()
    survey_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MonthlyWin
        fields = [
            'id', 'name', 'status', 'status_display',
            'phase1_deadline', 'phase2_deadline',
            'week_count', 'survey_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'status_display', 'week_count', 'survey_count', 'created_at', 'updated_at']

    def get_week_count(self, obj):
        return obj.wins.count()

    def get_survey_count(self, obj):
        return obj.surveys.count()


class MonthlyWinDetailSerializer(MonthlyWinSerializer):
    wins = WinSerializer(many=True, read_only=True)
    surveys = MonthlyWinSurveySerializer(many=True, read_only=True)
    results = MonthlyWinResultSerializer(many=True, read_only=True)

    class Meta(MonthlyWinSerializer.Meta):
        fields = MonthlyWinSerializer.Meta.fields + ['wins', 'surveys', 'results']
