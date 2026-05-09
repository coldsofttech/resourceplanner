from django.apps import AppConfig


class ResourcePlanConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.resource_plans"
    verbose_name = "Resource Plan"
    label = "resource_plans"

    def ready(self):
        import apps.resource_plans.signals  # noqa: F401
