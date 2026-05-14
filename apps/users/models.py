from django.contrib.auth import get_user_model
from django.db import models

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
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text='Profile picture uploaded by the user.',
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text='When True, the user is forced to change their password on next login.',
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


class UserGroup(models.Model):
    """
    Application-level user groups / roles.
    ADMINISTRATOR is the built-in system group with full access.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    is_admin_group = models.BooleanField(
        default=False,
        help_text='Members of admin groups receive staff-level access across the application.',
    )
    is_system = models.BooleanField(
        default=False,
        help_text='System groups are created automatically and cannot be deleted.',
    )
    members = models.ManyToManyField(
        User,
        through='UserGroupMembership',
        related_name='user_groups',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserGroupMembership(models.Model):
    """Through model tracking when a user joined a group."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_memberships',
    )
    group = models.ForeignKey(
        UserGroup,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'group')]
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user.email} → {self.group.name}'
