from django.apps import AppConfig


class SprintCapacityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sprint_capacity'
    label = 'sprint_capacity'

    def ready(self):
        import apps.sprint_capacity.signals as signals  # noqa: F401 — registers all signal handlers

        # signals.register_leave_signals()
