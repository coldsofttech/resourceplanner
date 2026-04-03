from django.core.validators import RegexValidator
from django.db import models

_CODE_VALIDATOR = RegexValidator(
    regex=r'^[A-Z][A-Z0-9_]*$',
    message=(
        'Code must start with an uppercase letter and contain only '
        'uppercase letters, digits, and underscores (e.g. DEFAULT_HOLIDAYS).'
    ),
)


class Configuration(models.Model):
    """
    Structure:
    * code: TEXT NOT NULL UNIQUE 50 CHARS
    * label: TEXT NOT NULL 120 CHARS
    * value: TEXT NOT NULL
    * description: TEXT
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        validators=[_CODE_VALIDATOR],
        help_text='Unique UPPER_SNAKE_CASE key, e.g., DEFAULT_HOLIDAYS.',
    )
    label = models.CharField(
        max_length=120,
        help_text='Short human-readable label for this configuration.',
    )
    value = models.CharField(
        help_text='Stored value (always a string; cast to the appropriate type when used).',
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
        ordering = ['code']

    def __str__(self):
        return f"{self.code} = {self.value}"
