from django.db import models

SCENARIO_USER_CREATED = 'user_created'
SCENARIO_PASSWORD_RESET = 'password_reset'
SCENARIO_RECHARGE_FORECAST = 'recharge_forecast'
SCENARIO_RECHARGE_ACTUALS = 'recharge_actuals'
SCENARIO_ONBOARDING_SUBMITTED = 'onboarding_submitted'

SCENARIO_CHOICES = [
    (SCENARIO_USER_CREATED, 'New User Created'),
    (SCENARIO_PASSWORD_RESET, 'Password Reset'),
    (SCENARIO_RECHARGE_FORECAST, 'Recharge Forecast'),
    (SCENARIO_RECHARGE_ACTUALS, 'Recharge Actuals'),
    (SCENARIO_ONBOARDING_SUBMITTED, 'Onboarding Submitted'),
]

TABLE_SCENARIOS = {SCENARIO_RECHARGE_FORECAST, SCENARIO_RECHARGE_ACTUALS}


class EmailTemplateHeader(models.Model):
    """Reusable HTML header block that can be attached to any template."""
    name = models.CharField(max_length=200, unique=True)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EmailTemplateFooter(models.Model):
    """Reusable HTML footer block that can be attached to any template."""
    name = models.CharField(max_length=200, unique=True)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EmailTemplate(models.Model):
    """
    One template per email scenario. Body is HTML with {{ variable }} placeholders.
    table_config stores column/display preferences for recharge table blocks.
    """
    scenario = models.CharField(
        max_length=50,
        choices=SCENARIO_CHOICES,
        unique=True,
    )
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    header = models.ForeignKey(
        EmailTemplateHeader,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='templates',
    )
    footer = models.ForeignKey(
        EmailTemplateFooter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='templates',
    )
    table_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Column/display config for {{ recharge_table }} blocks in recharge scenarios.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scenario']

    def __str__(self):
        return f'Email Template — {self.get_scenario_display()}'
