from django.conf import settings
from django.db import models


class Roadmap(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmaps',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class RoadmapItem(models.Model):
    TYPE_PROJECT = 'project'
    TYPE_MILESTONE = 'milestone'
    TYPE_PLACEHOLDER = 'placeholder'

    TYPE_CHOICES = [
        (TYPE_PROJECT, 'Project'),
        (TYPE_MILESTONE, 'Milestone'),
        (TYPE_PLACEHOLDER, 'Placeholder'),
    ]

    roadmap = models.ForeignKey(
        Roadmap,
        on_delete=models.CASCADE,
        related_name='items',
    )
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PROJECT)
    name = models.CharField(max_length=200)
    # Linked real project — read-only reference; changes here do not propagate back to Projects
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_items',
    )
    programme = models.ForeignKey(
        'programmes.Programme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_items',
    )
    assigned_team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_items',
    )
    start_sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_items_start',
    )
    end_sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_items_end',
    )
    # Free-text grouping category (e.g. "Wave 1", "Platform", "BAU")
    category = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=7, blank=True, default='')  # hex e.g. #6366f1
    display_order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f'{self.roadmap.name} / {self.name}'


class RoadmapMilestone(models.Model):
    """A key event or gate pinned to a sprint within a roadmap item."""
    roadmap_item = models.ForeignKey(
        RoadmapItem,
        on_delete=models.CASCADE,
        related_name='milestones',
    )
    name = models.CharField(max_length=200)
    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roadmap_milestones',
    )
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sprint__start_date', 'id']

    def __str__(self):
        return f'{self.roadmap_item.name} — {self.name}'
