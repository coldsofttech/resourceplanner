import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ProjectSubStatusesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.project_sub_statuses'
    label = 'project_sub_statuses'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_defaults, sender=self)


def _seed_defaults(sender, **kwargs):
    from django.db import transaction
    from apps.project_sub_statuses.services import PROJECT_SUB_STATUS_DEFAULTS
    from apps.project_sub_statuses.models import ProjectSubStatus

    with transaction.atomic():
        for code, meta in PROJECT_SUB_STATUS_DEFAULTS.items():
            try:
                ProjectSubStatus.objects.update_or_create(
                    name=meta["name"],
                    main_status=meta["main_status"],
                    defaults={
                        "order": meta["order"],
                        "is_active": meta["is_active"],
                    }
                )
            except Exception as e:
                logger.exception(f"Failed to create default configuration for {code}: {e}")
