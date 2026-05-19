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
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=500)),
                ('body', models.TextField(blank=True)),
                ('link', models.CharField(blank=True, max_length=1000)),
                ('notification_type', models.CharField(
                    choices=[
                        ('comment_mention',   'Comment Mention'),
                        ('project_approved',  'Project Approved'),
                        ('recharge_forecast', 'Recharge Forecast'),
                        ('recharge_actuals',  'Recharge Actuals'),
                        ('project_follow',    'Project Update'),
                    ],
                    max_length=50,
                )),
                ('is_read',      models.BooleanField(default=False)),
                ('is_dismissed', models.BooleanField(default=False)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
