import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0008_projectactuals_ignore_previous_fy_cost'),
        ('projects', '0014_project_completed_sprint'),
        ('sprints', '0002_sprint_closed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RechargeProjectGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_recharge_groups',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('projects', models.ManyToManyField(
                    blank=True,
                    related_name='recharge_groups',
                    to='projects.project',
                )),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='RechargeEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                    max_length=10,
                )),
                ('to_emails', models.JSONField(default=list)),
                ('cc_emails', models.JSONField(default=list)),
                ('subject', models.CharField(max_length=500)),
                ('body', models.TextField()),
                ('status', models.CharField(
                    choices=[('PENDING', 'Pending'), ('SENT', 'Sent'), ('ERROR', 'Error')],
                    default='PENDING',
                    max_length=10,
                )),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('triggered_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='emails',
                    to='sprint_forecast.rechargeprojectgroup',
                )),
                ('project', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recharge_emails',
                    to='projects.project',
                )),
                ('sprint', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recharge_emails',
                    to='sprints.sprint',
                )),
                ('triggered_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='triggered_recharge_emails',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-triggered_at']},
        ),
    ]
