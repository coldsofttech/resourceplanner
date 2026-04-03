from django.db import models


class TeamRole(models.Model):
    """
    Structure:
    * role: TEXT NOT NULL UNIQUE 100 CHARS
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    role = models.CharField(
        max_length=100,
        unique=True,
        help_text='Role name, max 100 characters. e.g. Senior Engineer',
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
        ordering = ['role']

    def __str__(self):
        return self.role
