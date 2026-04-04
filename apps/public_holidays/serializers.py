from rest_framework import serializers

from .models import PublicHoliday
from ..office_locations.models import OfficeLocation
from ..office_locations.serializers import OfficeLocationSerializer


class PublicHolidaySerializer(serializers.ModelSerializer):
    """
    Full serializer for PublicHoliday — used for list, retrieve, create, update.
    Accepts location as a PK; returns it as a nested object.
    """
    location = serializers.PrimaryKeyRelatedField(
        queryset=OfficeLocation.objects.all(),
    )

    class Meta:
        model = PublicHoliday
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['location'] = OfficeLocationSerializer(instance.location).data
        return rep

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Holiday name is required.")
        if len(name) > 120:
            raise serializers.ValidationError("Holiday name must be 120 characters or fewer.")
        return name

    def validate(self, attrs):
        # Check uniqueness of (location, date) manually so we can surface a clean error.
        location = attrs.get('location') or (self.instance.location if self.instance else None)
        date = attrs.get('date') or (self.instance.date if self.instance else None)

        qs = PublicHoliday.objects.filter(location=location, date=date)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"A public holiday for {location} on {date} already exists."
            )
        return attrs


class PublicHolidayExportSerializer(serializers.ModelSerializer):
    """
    Flat serializer used for CSV / PDF export — all FK values as readable strings.
    """
    location = serializers.PrimaryKeyRelatedField(
        queryset=OfficeLocation.objects.all()
    )

    class Meta:
        model = PublicHoliday
        fields = ['id', 'location', 'date', 'name']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        location = OfficeLocationSerializer(instance.location).data
        rep["location"] = f"{location.get('city')}, {location.get('country')}"
        return rep
