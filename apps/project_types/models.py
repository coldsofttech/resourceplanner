from django.db import models


class ProjectType(models.Model):
    """
    Structure:
    * name: TEXT NOT NULL UNIQUE 60 CHARS
    * description: TEXT
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    name = models.CharField(
        max_length=60,
        unique=True
    )
    description = models.CharField(
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
