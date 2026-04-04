from django.apps import AppConfig


class MemberLeavesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.member_leaves'
    label = 'member_leaves'

    def ready(self):
        import apps.member_leaves.signals  # noqa: F401 — registers signal handlers
