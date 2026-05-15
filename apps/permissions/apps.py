import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

EXTRA_PERMISSIONS = [
    # (app_label, model_name, codename, name)
    ('delivery_teams', 'deliveryteam', 'export', 'Can export delivery team'),
    ('team_members', 'teammember', 'export', 'Can export team member'),
    ('team_members', 'teammember', 'import', 'Can import team member'),
    ('member_leaves', 'memberleave', 'export', 'Can export member leave'),
    ('member_leaves', 'memberleave', 'add_own', 'Can add own leave'),
    ('member_leaves', 'memberleave', 'add_behalf', 'Can add leave on behalf of others'),
    ('financial_years', 'financialyear', 'export', 'Can export financial year'),
    ('sprints', 'sprint', 'export', 'Can export sprint'),
    ('sprints', 'sprint', 'execute', 'Can execute sprint plan'),
    ('sprints', 'sprint', 'run', 'Can run sprint analysis'),
    ('sprint_capacity', 'sprintcapacity', 'export', 'Can export sprint capacity'),
    ('resource_plans', 'resourceplan', 'export', 'Can export resource plan'),
    ('resource_plans', 'resourceplan', 'execute', 'Can execute resource plan'),
    ('resource_plans', 'resourceplan', 'run', 'Can run resource plan engine'),
    ('projects', 'project', 'export', 'Can export project'),
    ('projects', 'project', 'import', 'Can import project'),
    ('programmes', 'programme', 'export', 'Can export programme'),
    ('contacts', 'contact', 'export', 'Can export contact'),
    ('contacts', 'contact', 'import', 'Can import contact'),
    ('skills', 'skill', 'export', 'Can export skill'),
    ('skills', 'skill', 'import', 'Can import skill'),
    ('team_roles', 'teamrole', 'export', 'Can export team role'),
    ('team_roles', 'teamrole', 'import', 'Can import team role'),
    ('office_locations', 'officelocation', 'export', 'Can export location'),
    ('office_locations', 'officelocation', 'import', 'Can import location'),
    ('employment_types', 'employmenttype', 'export', 'Can export employment type'),
    ('employment_types', 'employmenttype', 'import', 'Can import employment type'),
    ('project_types', 'projecttype', 'export', 'Can export project type'),
    ('project_types', 'projecttype', 'import', 'Can import project type'),
    ('project_sub_statuses', 'projectsubstatus', 'export', 'Can export project sub status'),
    ('project_sub_statuses', 'projectsubstatus', 'import', 'Can import project sub status'),
    ('public_holidays', 'publicholiday', 'export', 'Can export public holiday'),
    ('public_holidays', 'publicholiday', 'import', 'Can import public holiday'),
]


class PermissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.permissions'
    label = 'permissions'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_permissions, sender=self)


def _seed_permissions(sender, **kwargs):
    from django.db import transaction
    try:
        with transaction.atomic():
            _ensure_extra_permissions()
    except Exception as exc:
        logger.exception('Permission seeder failed: %s', exc)


def _ensure_extra_permissions():
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    for app_label, model_name, codename, name in EXTRA_PERMISSIONS:
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
            Permission.objects.get_or_create(
                content_type=ct,
                codename=codename,
                defaults={'name': name},
            )
        except ContentType.DoesNotExist:
            logger.warning('ContentType not found for %s.%s — skipping.', app_label, model_name)
        except Exception as exc:
            logger.warning('Could not create permission %s.%s.%s: %s', app_label, model_name, codename, exc)
