from django.db import models


class EmploymentType(models.Model):
    """
    Structure:
    * name: TEXT NOT NULL UNIQUE 100 CHARS
    * is_active: BOOLEAN DEFAULT (TRUE)
    * is_default: BOOLEAN DEFAULT (FALSE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Employment type name, max 100 characters. e.g. Full-time Permanent',
    )
    is_active = models.BooleanField(
        default=True
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Only one employment type may be the default at a time. Used to pre-select in UI dropdowns.',
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
