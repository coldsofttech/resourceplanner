from rest_framework import serializers
from .models import Roadmap, RoadmapItem, RoadmapMilestone


class RoadmapMilestoneSerializer(serializers.ModelSerializer):
    sprint_name = serializers.SerializerMethodField()
    sprint_number = serializers.SerializerMethodField()
    sprint_start_date = serializers.SerializerMethodField()

    class Meta:
        model = RoadmapMilestone
        fields = [
            'id', 'roadmap_item', 'name', 'sprint', 'sprint_name',
            'sprint_number', 'sprint_start_date', 'is_complete',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_sprint_name(self, obj):
        return obj.sprint.sprint_name if obj.sprint_id else None

    def get_sprint_number(self, obj):
        return obj.sprint.sprint_number if obj.sprint_id else None

    def get_sprint_start_date(self, obj):
        return obj.sprint.start_date.isoformat() if obj.sprint_id else None


class RoadmapItemSerializer(serializers.ModelSerializer):
    milestones = RoadmapMilestoneSerializer(many=True, read_only=True)
    project_name = serializers.SerializerMethodField()
    programme_name = serializers.SerializerMethodField()
    assigned_team_name = serializers.SerializerMethodField()
    start_sprint_name = serializers.SerializerMethodField()
    start_sprint_date = serializers.SerializerMethodField()
    end_sprint_name = serializers.SerializerMethodField()
    end_sprint_date = serializers.SerializerMethodField()
    item_type_display = serializers.SerializerMethodField()

    class Meta:
        model = RoadmapItem
        fields = [
            'id', 'roadmap', 'item_type', 'item_type_display', 'name',
            'project', 'project_name',
            'programme', 'programme_name',
            'assigned_team', 'assigned_team_name',
            'start_sprint', 'start_sprint_name', 'start_sprint_date',
            'end_sprint', 'end_sprint_name', 'end_sprint_date',
            'category', 'color', 'display_order', 'notes',
            'milestones', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_item_type_display(self, obj):
        return obj.get_item_type_display()

    def get_project_name(self, obj):
        return obj.project.name if obj.project_id else None

    def get_programme_name(self, obj):
        return obj.programme.name if obj.programme_id else None

    def get_assigned_team_name(self, obj):
        return obj.assigned_team.name if obj.assigned_team_id else None

    def get_start_sprint_name(self, obj):
        return obj.start_sprint.sprint_name if obj.start_sprint_id else None

    def get_start_sprint_date(self, obj):
        return obj.start_sprint.start_date.isoformat() if obj.start_sprint_id else None

    def get_end_sprint_name(self, obj):
        return obj.end_sprint.sprint_name if obj.end_sprint_id else None

    def get_end_sprint_date(self, obj):
        return obj.end_sprint.end_date.isoformat() if obj.end_sprint_id else None


class RoadmapSerializer(serializers.ModelSerializer):
    items = RoadmapItemSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Roadmap
        fields = [
            'id', 'name', 'description', 'created_by', 'created_by_name',
            'item_count', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by_id:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_item_count(self, obj):
        return obj.items.count()


class RoadmapListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the list endpoint (no nested items)."""
    created_by_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Roadmap
        fields = [
            'id', 'name', 'description', 'created_by', 'created_by_name',
            'item_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by_id:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_item_count(self, obj):
        return obj.items.count()
