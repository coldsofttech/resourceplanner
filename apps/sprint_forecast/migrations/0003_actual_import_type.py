import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0002_remove_recharge_label'),
        ('sprints', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add import_type to ForecastImport
        migrations.AddField(
            model_name='forecastimport',
            name='import_type',
            field=models.CharField(
                choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                default='FORECAST',
                max_length=10,
            ),
        ),
        # 2. Remove old unique constraint on ForecastImport
        migrations.RemoveConstraint(
            model_name='forecastimport',
            name='unique_forecast_import_version',
        ),
        # 3. Add new unique constraint including import_type on ForecastImport
        migrations.AddConstraint(
            model_name='forecastimport',
            constraint=models.UniqueConstraint(
                fields=['sprint', 'team', 'import_type', 'version_number'],
                name='unique_forecast_import_version',
            ),
        ),
        # 4. Add import_type to SprintForecastRow
        migrations.AddField(
            model_name='sprintforecastrow',
            name='import_type',
            field=models.CharField(
                choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                default='FORECAST',
                max_length=10,
            ),
        ),
        # 5. Create SprintActualReviewComplete table
        migrations.CreateModel(
            name='SprintActualReviewComplete',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('override_applied', models.BooleanField(default=False)),
                ('override_notes', models.TextField(blank=True)),
                ('completed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='actual_review_completions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('sprint', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='actual_review_complete',
                    to='sprints.sprint',
                )),
            ],
        ),
    ]
