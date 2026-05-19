from django.core.validators import RegexValidator
from django.db import models

_CODE_VALIDATOR = RegexValidator(
    regex=r'^[A-Z][A-Z0-9_]*$',
    message=(
        'Code must start with an uppercase letter and contain only '
        'uppercase letters, digits, and underscores (e.g. DEFAULT_HOLIDAYS).'
    ),
)

DATA_TYPE_CHOICES = [
    ('string', 'String'),
    ('integer', 'Integer'),
    ('float', 'Float'),
    ('boolean', 'Boolean'),
]

MODULE_CHOICES = [
    ('general', 'General'),
    ('integration_ai', 'AI Integration'),
    ('integration_email', 'Email Integration'),
    ('integration_sso', 'SSO Integration'),
    ('integration_jira', 'Jira Integration'),
    ('security', 'Security'),
    ('security_password', 'Password Policy'),
    ('project_approval', 'Project Approval'),
]


class Configuration(models.Model):
    """
    Structure:
    * code: TEXT NOT NULL UNIQUE 50 CHARS
    * label: TEXT NOT NULL 120 CHARS
    * value: TEXT NOT NULL (encrypted if is_secret=True)
    * description: TEXT
    * data_type: TEXT — string | integer | float | boolean
    * is_secret: BOOL — if True, value is encrypted at rest
    * module: TEXT — logical grouping (general | integration_* | security | security_password)
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
        blank=True,
        help_text=(
            'Stored value (always a string). '
            'Encrypted at rest when is_secret=True; cast to the appropriate type when used.'
        ),
    )
    description = models.CharField(
        blank=True
    )
    data_type = models.CharField(
        max_length=10,
        choices=DATA_TYPE_CHOICES,
        default='string',
        help_text='Expected data type of the stored value.',
    )
    is_secret = models.BooleanField(
        default=False,
        help_text='If true, the value is treated as a secret and stored encrypted.',
    )
    module = models.CharField(
        max_length=30,
        choices=MODULE_CHOICES,
        default='general',
        help_text='Logical grouping: general, integration_*, security, or security_password.',
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
        if self.is_secret and self.value:
            return f'{self.code} = ••••••••'
        return f'{self.code} = {self.value}'
