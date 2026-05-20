from django.conf import settings
from django.db import models


class OrgChartNode(models.Model):
    TYPE_MEMBER = 'member'
    TYPE_TEAM   = 'team'
    TYPE_CHOICES = [(TYPE_MEMBER, 'Member'), (TYPE_TEAM, 'Team')]

    node_type   = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_MEMBER)
    name        = models.CharField(max_length=200)
    job_title   = models.CharField(max_length=200, blank=True)
    email       = models.CharField(max_length=254, blank=True)
    avatar_url  = models.CharField(max_length=500, blank=True)

    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orgchart_nodes',
    )
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    team_member = models.ForeignKey(
        'team_members.TeamMember',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orgchart_nodes',
    )

    is_vacant  = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orgchart_nodes_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        vacant = ' [Vacant]' if self.is_vacant else ''
        return f'{self.name}{vacant}'
