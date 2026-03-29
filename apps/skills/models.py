from django.db import models


class Skill(models.Model):
    """
    Structure:
    * skill: TEXT NOT NULL UNIQUE 20 CHARS
    * description: TEXT
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    skill = models.CharField(
        max_length=20,
        unique=True,
        help_text='Uppercase code, max 20 characters. e.g. AWSENGINEER',
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
        ordering = ['skill']

    def __str__(self):
        return self.skill
