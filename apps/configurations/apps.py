from django.apps import AppConfig


class ConfigurationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configurations'
    label = 'configurations'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_defaults, sender=self)


def _seed_defaults(sender, **kwargs):
    try:
        from apps.configurations.services import CONFIGURATION_DEFAULTS
        for code, meta in CONFIGURATION_DEFAULTS.items():
            from apps.configurations.models import Configuration
            Configuration.objects.get_or_create(
                code=code,
                defaults={
                    "label": meta["label"],
                    "value": meta["value"],
                    "description": meta["description"],
                }
            )
    except Exception:
        pass
