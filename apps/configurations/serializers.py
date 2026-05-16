import re

from rest_framework import serializers

from .encryption import is_encrypted
from .models import Configuration

_SECRET_MASK = '••••••••'


class ConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for configurations.
    Secret values are masked in output; raw plaintext is never returned to the client.
    """

    class Meta:
        model = Configuration
        fields = '__all__'
        read_only_fields = [
            'code', 'label', 'description',
            'data_type', 'is_secret', 'module',
            'created_at', 'updated_at',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_secret:
            data['value'] = _SECRET_MASK if instance.value else ''
        return data

    def validate_code(self, value):
        code = value.strip().upper()
        if not re.match(r'^[A-Z][A-Z0-9_]*$', code):
            raise serializers.ValidationError(
                'Code must start with an uppercase letter and contain only '
                'uppercase letters, digits, and underscores.'
            )
        if len(code) > 50:
            raise serializers.ValidationError('Code must be 50 characters or fewer.')
        return code

    def validate_value(self, value):
        instance = self.instance

        # Secrets allow an empty submission (means "keep existing encrypted value")
        if instance and instance.is_secret:
            return str(value).strip() if value else ''

        # Non-secrets require a non-blank value
        if str(value).strip() == '':
            raise serializers.ValidationError('Value cannot be blank.')

        value = str(value).strip()

        # Data-type validation
        if instance:
            dt = instance.data_type
            if dt == 'integer':
                try:
                    int(value)
                except ValueError:
                    raise serializers.ValidationError('Value must be a valid integer.')
            elif dt == 'float':
                try:
                    float(value)
                except ValueError:
                    raise serializers.ValidationError('Value must be a valid decimal number.')
            elif dt == 'boolean':
                if value.lower() not in ('true', 'false'):
                    raise serializers.ValidationError("Value must be 'true' or 'false'.")

        return value

    def update(self, instance, validated_data):
        validated_data.pop('code', None)
        return super().update(instance, validated_data)


class ConfigurationExportSerializer(serializers.ModelSerializer):
    """
    Export-specific serializer for configurations.
    Secret values are replaced with a protection placeholder.
    """

    class Meta:
        model = Configuration
        fields = ['id', 'code', 'label', 'data_type', 'is_secret', 'description', 'value']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_secret:
            data['value'] = '[PROTECTED]'
        return data
