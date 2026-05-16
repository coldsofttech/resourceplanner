import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ConfigurationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configurations'
    label = 'configurations'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_defaults, sender=self)


def _seed_defaults(sender, **kwargs):
    from django.db import transaction
    from apps.configurations.models import Configuration
    from apps.configurations.services import CONFIGURATION_DEFAULTS

    with transaction.atomic():
        for code, meta in CONFIGURATION_DEFAULTS.items():
            try:
                obj, created = Configuration.objects.get_or_create(
                    code=code,
                    defaults={
                        "label": meta["label"],
                        "value": meta["value"],
                        "description": meta["description"],
                        "data_type": meta.get("data_type", "string"),
                        "is_secret": meta.get("is_secret", False),
                        "module": meta.get("module", "general"),
                    },
                )
                if not created:
                    # Update metadata fields only; preserve any user-set (or encrypted) value.
                    obj.label = meta["label"]
                    obj.description = meta["description"]
                    obj.data_type = meta.get("data_type", "string")
                    obj.is_secret = meta.get("is_secret", False)
                    obj.module = meta.get("module", "general")
                    obj.save(update_fields=["label", "description", "data_type", "is_secret", "module"])
            except Exception as e:
                logger.exception("Failed to seed default configuration for %s: %s", code, e)
