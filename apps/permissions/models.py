from django.contrib.auth.models import Permission
from django.db import models

MODULE_CHOICES = [
    ('delivery_teams', 'Delivery Teams'),
    ('team_members', 'Team Members'),
    ('member_leaves', 'Member Leaves'),
    ('financial_years', 'Financial Years'),
    ('sprints', 'Sprints'),
    ('sprint_capacity', 'Sprint Capacity'),
    ('resource_plans', 'Resource Plans'),
    ('projects', 'Projects'),
    ('programmes', 'Programmes'),
    ('contacts', 'Contacts'),
    ('skills', 'Skills'),
    ('team_roles', 'Team Roles'),
    ('office_locations', 'Office Locations'),
    ('employment_types', 'Employment Types'),
    ('project_types', 'Project Types'),
    ('project_sub_statuses', 'Project Sub-Statuses'),
    ('public_holidays', 'Public Holidays'),
]


SCOPE_CHOICES = [
    ('all', 'All — no restriction'),
    ('team', 'Team — own delivery team only'),
    ('self', 'Self — own records only'),
]


class PermissionCategory(models.Model):
    module = models.CharField(
        max_length=50,
        choices=MODULE_CHOICES,
        blank=True,
        default='',
        help_text='Application module this category belongs to.',
    )
    scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default='all',
        help_text='Data scope this category grants: all records, team records, or own records only.',
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='categories',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Permission categories'

    def __str__(self):
        return self.name
