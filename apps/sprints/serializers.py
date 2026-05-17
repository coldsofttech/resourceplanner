from rest_framework import serializers

from .models import Sprint


class SprintSerializer(serializers.ModelSerializer):
    """Full sprint serializer — used for create / retrieve / update."""
    fy_long = serializers.CharField(source='financial_year.long_fy', read_only=True)
    fy_short = serializers.CharField(source='financial_year.short_fy', read_only=True)
    remaining_days = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Sprint
        fields = '__all__'
        read_only_fields = [
            'month', 'created_at', 'updated_at', 'remaining_days',
            'fy_long', 'fy_short', 'is_closed', 'closed_at', 'closed_by',
        ]

    def get_remaining_days(self, obj) -> int | None:
        from django.utils import timezone
        today = timezone.localdate()
        if obj.end_date < today:
            return 0
        if obj.start_date > today:
            return (obj.end_date - obj.start_date).days + 1
        return (obj.end_date - today).days + 1

    def validate(self, data):
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_date': 'End date must be after start date.'}
            )
        return data


class SprintSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdown / navbar use."""
    fy_short = serializers.CharField(source='financial_year.short_fy', read_only=True)

    class Meta:
        model = Sprint
        fields = ['id', 'sprint_name', 'sprint_number', 'start_date', 'end_date', 'is_active', 'fy_short']


class SprintExportSerializer(serializers.ModelSerializer):
    fy_long = serializers.CharField(source='financial_year.long_fy', read_only=True)
    remaining_days = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Sprint
        fields = ['id', 'fy_long', 'sprint_number', 'sprint_name', 'start_date', 'end_date', 'month', 'is_active',
                  'is_overridden', 'notes', 'remaining_days']

    def get_remaining_days(self, obj) -> int | None:
        from django.utils import timezone
        today = timezone.localdate()
        if obj.end_date < today:
            return 0
        if obj.start_date > today:
            return (obj.end_date - obj.start_date).days + 1
        return (obj.end_date - today).days + 1
