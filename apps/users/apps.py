import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = 'admin@resourceplanner.com'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'ReP1Adm$n'
ADMINISTRATOR_GROUP_NAME = 'ADMINISTRATOR'


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    label = 'users'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_users, sender=self)


def _seed_users(sender, **kwargs):
    from django.db import transaction
    try:
        with transaction.atomic():
            _ensure_administrator_group()
            _ensure_default_admin()
    except Exception as exc:
        logger.exception('User seeder failed: %s', exc)


def _ensure_administrator_group():
    from apps.users.models import UserGroup
    group, created = UserGroup.objects.get_or_create(
        name=ADMINISTRATOR_GROUP_NAME,
        defaults={
            'description': 'Built-in administrator group. Members have full access to the application.',
            'is_admin_group': True,
            'is_system': True,
        },
    )
    if not created:
        # Ensure system flags are always set correctly
        updated = False
        if not group.is_admin_group:
            group.is_admin_group = True
            updated = True
        if not group.is_system:
            group.is_system = True
            updated = True
        if updated:
            group.save(update_fields=['is_admin_group', 'is_system'])
    return group


def _ensure_default_admin():
    from django.contrib.auth import get_user_model
    from apps.users.models import UserGroup, UserProfile

    User = get_user_model()

    user, created = User.objects.get_or_create(
        username=DEFAULT_ADMIN_USERNAME,
        defaults={
            'email': DEFAULT_ADMIN_EMAIL,
            'first_name': 'Admin',
            'last_name': '',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        },
    )

    if created:
        user.set_password(DEFAULT_ADMIN_PASSWORD)
        user.save()
        logger.info('Created default admin user: %s', DEFAULT_ADMIN_EMAIL)
    else:
        # Ensure existing admin user has correct flags
        changed = []
        if not user.is_staff:
            user.is_staff = True
            changed.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed.append('is_superuser')
        if not user.email:
            user.email = DEFAULT_ADMIN_EMAIL
            changed.append('email')
        if changed:
            user.save(update_fields=changed)

    # Ensure profile with must_change_password=True on first creation
    profile, profile_created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'must_change_password': True},
    )
    if profile_created:
        logger.info('Created profile for default admin, forcing password change on first login.')

    # Ensure admin is in the ADMINISTRATOR group
    try:
        admin_group = UserGroup.objects.get(name=ADMINISTRATOR_GROUP_NAME)
        admin_group.members.add(user)
    except UserGroup.DoesNotExist:
        pass
