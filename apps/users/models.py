from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserProfile(models.Model):
    """
    Extends Django's built-in User with SSO identity linkage.
    Classic (username/password) users have empty sso_provider and sso_uid.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    sso_provider = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Identity provider name, e.g. "GitHub", "Azure AD". Empty for classic users.',
    )
    sso_uid = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Unique identifier from the identity provider.',
    )
    avatar_url = models.URLField(
        blank=True,
        default='',
        help_text='Profile picture URL from the identity provider (optional).',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sso_provider', 'sso_uid'],
                condition=models.Q(sso_provider__gt=''),
                name='unique_sso_identity',
            )
        ]

    def __str__(self):
        if self.sso_provider:
            return f'{self.user.username} ({self.sso_provider})'
        return self.user.username
