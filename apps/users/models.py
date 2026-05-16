import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models


def _avatar_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
    return f'avatars/{uuid.uuid4().hex}.{ext}'

User = get_user_model()


class UserProfile(models.Model):
    """
    Extends Django's built-in User with SSO identity linkage and auth flags.
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
    avatar = models.ImageField(
        upload_to=_avatar_upload_path,
        blank=True,
        null=True,
        help_text='Profile picture uploaded by the user.',
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text='When True, the user is forced to change their password on next login.',
    )
    password_last_changed = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp of the last password change. Used for rotation policy enforcement.',
    )
    permission_categories = models.ManyToManyField(
        'permissions.PermissionCategory',
        blank=True,
        related_name='user_profiles',
        help_text='Permission categories assigned directly to this user.',
    )
    timezone = models.CharField(
        max_length=64,
        default='UTC',
        help_text='User timezone for displaying datetimes (e.g. Europe/London).',
    )
    theme = models.CharField(
        max_length=10,
        choices=[('light', 'Light'), ('dark', 'Dark')],
        default='light',
        help_text='UI theme preference.',
    )
    dashboard_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Per-user dashboard widget configuration.',
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


class PasswordHistory(models.Model):
    """Stores hashed previous passwords to prevent reuse."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_history',
    )
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class GroupProfile(models.Model):
    """Extends Django's built-in auth.Group with metadata for application-level role management."""
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    description = models.TextField(blank=True, default='')
    is_admin_group = models.BooleanField(
        default=False,
        help_text='Members of admin groups receive staff-level access across the application.',
    )
    is_system = models.BooleanField(
        default=False,
        help_text='System groups are created automatically and cannot be deleted.',
    )
    permission_categories = models.ManyToManyField(
        'permissions.PermissionCategory',
        blank=True,
        related_name='groups',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group__name']

    def __str__(self):
        return self.group.name
