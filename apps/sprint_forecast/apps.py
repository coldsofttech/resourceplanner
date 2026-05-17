from django.apps import AppConfig


class SprintForecastConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sprint_forecast'
    verbose_name = 'Sprint Forecast'

    def ready(self):
        import apps.sprint_forecast.signals  # noqa: F401
