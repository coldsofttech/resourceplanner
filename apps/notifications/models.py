from django.conf import settings
from django.db import models


class Notification(models.Model):
    TYPE_COMMENT_MENTION   = 'comment_mention'
    TYPE_PROJECT_APPROVED  = 'project_approved'
    TYPE_RECHARGE_FORECAST = 'recharge_forecast'
    TYPE_RECHARGE_ACTUALS  = 'recharge_actuals'
    TYPE_PROJECT_FOLLOW    = 'project_follow'

    TYPE_CHOICES = [
        (TYPE_COMMENT_MENTION,   'Comment Mention'),
        (TYPE_PROJECT_APPROVED,  'Project Approved'),
        (TYPE_RECHARGE_FORECAST, 'Recharge Forecast'),
        (TYPE_RECHARGE_ACTUALS,  'Recharge Actuals'),
        (TYPE_PROJECT_FOLLOW,    'Project Update'),
    ]

    user              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title             = models.CharField(max_length=500)
    body              = models.TextField(blank=True)
    link              = models.CharField(max_length=1000, blank=True)
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    is_read           = models.BooleanField(default=False)
    is_dismissed      = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.notification_type}] {self.title} → {self.user_id}'
