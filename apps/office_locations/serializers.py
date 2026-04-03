from rest_framework import serializers

from .models import OfficeLocation


class OfficeLocationSerializer(serializers.ModelSerializer):
    """
    Serializer for office locations.
    """

    class Meta:
        model = OfficeLocation
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate_city(self, value):
        city = value.strip()
        if len(city) > 100:
            raise serializers.ValidationError(
                "City must be 100 characters or fewer."
            )
        return city

    def validate_country(self, value):
        country = value.strip()
        if len(country) > 100:
            raise serializers.ValidationError(
                "Country must be 100 characters or fewer."
            )
        return country


class OfficeLocationExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for office locations.
    """

    class Meta:
        model = OfficeLocation
        fields = ['id', 'city', 'country', 'is_active']
