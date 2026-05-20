from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Todo, TodoComment

User = get_user_model()


class TodoCommentSerializer(serializers.ModelSerializer):
    created_by_name  = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model  = TodoComment
        fields = ['id', 'todo', 'content', 'created_by', 'created_by_name',
                  'created_by_email', 'created_at', 'updated_at']
        read_only_fields = ['id', 'todo', 'created_by', 'created_by_name',
                            'created_by_email', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class TodoSerializer(serializers.ModelSerializer):
    created_by_name   = serializers.SerializerMethodField()
    assigned_to_name  = serializers.SerializerMethodField()
    assigned_to_email = serializers.SerializerMethodField()
    status_display    = serializers.CharField(source='get_status_display', read_only=True)
    priority_display  = serializers.CharField(source='get_priority_display', read_only=True)
    is_overdue        = serializers.BooleanField(read_only=True)
    comment_count     = serializers.SerializerMethodField()

    class Meta:
        model  = Todo
        fields = [
            'id', 'title', 'description',
            'status', 'status_display',
            'priority', 'priority_display',
            'due_date', 'reminder_at', 'reminder_sent',
            'assigned_to', 'assigned_to_name', 'assigned_to_email',
            'created_by', 'created_by_name',
            'is_recurring', 'recurrence_rule', 'recurrence_interval',
            'recurrence_end_date', 'parent_todo',
            'is_overdue', 'completed_at', 'comment_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status_display', 'priority_display', 'reminder_sent',
            'created_by', 'created_by_name', 'assigned_to_name', 'assigned_to_email',
            'is_overdue', 'completed_at', 'comment_count',
            'created_at', 'updated_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.email
        return None

    def get_assigned_to_email(self, obj):
        return obj.assigned_to.email if obj.assigned_to else None

    def get_comment_count(self, obj):
        return obj.comments.count()


class TodoDetailSerializer(TodoSerializer):
    comments = TodoCommentSerializer(many=True, read_only=True)

    class Meta(TodoSerializer.Meta):
        fields = TodoSerializer.Meta.fields + ['comments']


class UserMentionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'email', 'name']

    def get_name(self, obj):
        return obj.get_full_name() or obj.email
