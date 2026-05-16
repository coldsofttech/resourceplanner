from django.contrib.auth.models import Permission
from django.db import models


class PermissionCategory(models.Model):
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
