from django.db import models


class BusinessUnit(models.Model):
    full_name = models.CharField(max_length=200, unique=True)
    short_name = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f'{self.short_name} — {self.full_name}'
