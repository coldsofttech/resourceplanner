import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ProgrammesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.programmes"
    label = "programmes"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(_seed_defaults, sender=self)


def _seed_defaults(sender, **kwargs):
    from django.db import transaction
    from apps.programmes.models import Programme

    with transaction.atomic():
        try:
            Programme.objects.update_or_create(
                name="Others",
                defaults={"is_active": True},
            )
        except Exception as e:
            logger.exception("Failed to seed default programme 'Others': %s", e)
