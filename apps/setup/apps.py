from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed_setup_complete(sender, **kwargs):
    """Mark SETUP_COMPLETE=true for existing deployments; leave false for fresh ones."""
    try:
        from django.contrib.auth import get_user_model
        from apps.configurations.models import Configuration

        if Configuration.objects.filter(code='SETUP_COMPLETE').exists():
            return

        User = get_user_model()
        has_users = User.objects.exists()
        Configuration.objects.create(
            code='SETUP_COMPLETE',
            label='Setup Complete',
            value='true' if has_users else 'false',
            data_type='boolean',
            is_secret=False,
            module='general',
            description='Marks whether the initial setup wizard has been completed.',
        )
    except Exception:
        pass


class SetupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.setup'
    verbose_name = 'Setup'

    def ready(self):
        # Connect without a sender so it fires after any app's migrations
        post_migrate.connect(_seed_setup_complete)
