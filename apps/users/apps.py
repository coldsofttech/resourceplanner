import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

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
