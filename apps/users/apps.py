import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_EMAIL = 'admin@resourceplanner.com'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'ReP1Adm$n'
ADMINISTRATOR_GROUP_NAME = 'ADMINISTRATOR'
GUEST_GROUP_NAME = 'GUEST'


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
            _ensure_guest_group()
            _ensure_default_admin()
    except Exception as exc:
        logger.exception('User seeder failed: %s', exc)


def _ensure_administrator_group():
    from django.contrib.auth.models import Group
    from apps.users.models import GroupProfile

    group, _ = Group.objects.get_or_create(name=ADMINISTRATOR_GROUP_NAME)
    profile, created = GroupProfile.objects.get_or_create(
        group=group,
        defaults={
            'description': 'Built-in administrator group. Members have full access to the application.',
            'is_admin_group': True,
            'is_system': True,
        },
    )
    if not created:
        updated = []
        if not profile.is_admin_group:
            profile.is_admin_group = True
            updated.append('is_admin_group')
        if not profile.is_system:
            profile.is_system = True
            updated.append('is_system')
        if updated:
            profile.save(update_fields=updated)
    return group


def _ensure_guest_group():
    from django.contrib.auth.models import Group
    from apps.users.models import GroupProfile

    group, _ = Group.objects.get_or_create(name=GUEST_GROUP_NAME)
    GroupProfile.objects.get_or_create(
        group=group,
        defaults={
            'description': 'Default group for self-registered and SSO users. Members have minimal access.',
            'is_admin_group': False,
            'is_system': True,
        },
    )
    return group


def _ensure_default_admin():
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from apps.users.models import UserProfile

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

    # Ensure profile exists; force password change only on first creation
    profile, profile_created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'must_change_password': True},
    )
    if profile_created:
        logger.info('Created profile for default admin, forcing password change on first login.')

    # Ensure admin is in the ADMINISTRATOR group
    try:
        admin_group = Group.objects.get(name=ADMINISTRATOR_GROUP_NAME)
        admin_group.user_set.add(user)
    except Group.DoesNotExist:
        pass
