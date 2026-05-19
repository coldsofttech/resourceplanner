from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'body', 'link',
            'notification_type', 'is_read', 'is_dismissed', 'created_at',
        ]
        read_only_fields = ['id', 'title', 'body', 'link', 'notification_type', 'created_at']
