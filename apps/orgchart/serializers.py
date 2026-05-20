from rest_framework import serializers
from .models import OrgChartNode


class OrgChartNodeSerializer(serializers.ModelSerializer):
    team_name        = serializers.SerializerMethodField()
    team_member_name = serializers.SerializerMethodField()
    children_count   = serializers.SerializerMethodField()

    class Meta:
        model  = OrgChartNode
        fields = [
            'id', 'node_type', 'name', 'job_title', 'email', 'avatar_url',
            'team', 'team_name',
            'parent',
            'team_member', 'team_member_name',
            'is_vacant', 'sort_order',
            'children_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'team_name', 'team_member_name', 'children_count', 'created_at', 'updated_at']

    def get_team_name(self, obj):
        return obj.team.name if obj.team else None

    def get_team_member_name(self, obj):
        return obj.team_member.display_name if obj.team_member else None

    def get_children_count(self, obj):
        return obj.children.count()
