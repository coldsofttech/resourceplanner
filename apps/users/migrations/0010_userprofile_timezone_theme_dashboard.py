from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_passwordhistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='timezone',
            field=models.CharField(
                default='UTC',
                max_length=64,
                help_text='User timezone for displaying datetimes (e.g. Europe/London).',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(
                choices=[('light', 'Light'), ('dark', 'Dark')],
                default='light',
                max_length=10,
                help_text='UI theme preference.',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='dashboard_config',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Per-user dashboard widget configuration.',
            ),
        ),
    ]
