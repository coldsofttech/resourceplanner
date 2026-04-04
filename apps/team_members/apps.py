from django.apps import AppConfig


class TeamMemberConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.team_members'
    label = 'team_members'

    def ready(self):
        import apps.team_members.signals  # noqa: F401 — registers signal handlers
