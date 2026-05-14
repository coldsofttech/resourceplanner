import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sso_provider', models.CharField(blank=True, default='', help_text='Identity provider name, e.g. "GitHub", "Azure AD". Empty for classic users.', max_length=100)),
                ('sso_uid', models.CharField(blank=True, default='', help_text='Unique identifier from the identity provider.', max_length=255)),
                ('avatar_url', models.URLField(blank=True, default='', help_text='Profile picture URL from the identity provider (optional).')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='userprofile',
            constraint=models.UniqueConstraint(
                condition=models.Q(sso_provider__gt=''),
                fields=['sso_provider', 'sso_uid'],
                name='unique_sso_identity',
            ),
        ),
    ]
