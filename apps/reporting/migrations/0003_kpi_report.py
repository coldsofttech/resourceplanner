import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_kpi_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.get_or_create(
        slug='kpi-estimate-accuracy',
        defaults={
            'name': 'KPI Report (Estimate % Accuracy)',
            'description': (
                'Review completed projects for a selected month and measure estimate '
                'accuracy based on total cost vs. estimate value.'
            ),
            'report_type': 'STANDARD',
            'is_active': True,
            'sort_order': 3,
        },
    )


def unseed_kpi_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.filter(slug='kpi-estimate-accuracy').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0002_sprint_fa_report'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0014_project_completed_sprint'),
    ]

    operations = [
        migrations.CreateModel(
            name='KPIReportComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(help_text='Month in YYYY-MM format (e.g. 2025-03).', max_length=7)),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_kpi_comments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_kpi_comments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='kpi_comments',
                    to='projects.project',
                )),
            ],
            options={
                'ordering': ['project__name'],
            },
        ),
        migrations.AddConstraint(
            model_name='kpireportcomment',
            constraint=models.UniqueConstraint(
                fields=['project', 'month'],
                name='unique_kpi_comment_project_month',
            ),
        ),
        migrations.RunPython(seed_kpi_report, reverse_code=unseed_kpi_report),
    ]
