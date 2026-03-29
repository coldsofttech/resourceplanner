from django.db import models


class DeliveryTeam(models.Model):
    """
    Structure:
    * name: TEXT NOT NULL UNIQUE 120 CHARS
    * description: TEXT
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    name = models.CharField(
        max_length=120,
        unique=True
    )
    description = models.CharField(
        blank=True
    )
    is_active = models.BooleanField(
        default=True
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
