from rest_framework import serializers

from .models import Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name is required and cannot be blank.")
        if len(value.strip()) > 200:
            raise serializers.ValidationError("Name must be 200 characters or fewer.")
        return value.strip()

    def validate_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email is required and cannot be blank.")
        return value.strip().lower()


class ContactSuggestSerializer(serializers.ModelSerializer):
    """Lightweight — for typeahead."""

    class Meta:
        model = Contact
        fields = ["id", "name", "email"]


class ContactExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "name", "email", "is_active"]
