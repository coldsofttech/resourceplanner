from rest_framework import serializers

from .models import FinancialYear


class FinancialYearSerializer(serializers.ModelSerializer):
    """Full serializer — used for list, retrieve, create, update."""
    remaining_days = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FinancialYear
        fields = '__all__'
        read_only_fields = [
            'long_fy',
            'short_fy',
            'span_days',
            'created_at',
            'updated_at',
        ]

    def get_remaining_days(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        if obj.end_date < today:
            return 0
        if obj.start_date > today:
            return obj.span_days
        return (obj.end_date - today).days + 1

    def validate(self, data):
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {'end_date': 'End date must be after start date.'}
            )
        return data


class FinancialYearSummarySerializer(serializers.ModelSerializer):
    """Compact serializer — used in navbar dropdowns and cross-module references."""

    class Meta:
        model = FinancialYear
        fields = ['id', 'long_fy', 'short_fy', 'is_active', 'start_date', 'end_date']


class FinancialYearExportSerializer(serializers.ModelSerializer):
    """Export-specific serializer."""
    remaining_days = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FinancialYear
        fields = [
            'id',
            'long_fy',
            'short_fy',
            'start_date',
            'end_date',
            'span_days',
            'remaining_days',
            'is_active',
            'notes',
        ]

    def get_remaining_days(self, obj):
        from django.utils import timezone
        today = timezone.localdate()
        if obj.end_date < today:
            return 0
        if obj.start_date > today:
            return obj.span_days
        return (obj.end_date - today).days + 1