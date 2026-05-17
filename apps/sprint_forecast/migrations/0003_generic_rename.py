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
        # ── Step 1: Rename model tables ───────────────────────────────────────
        migrations.RenameModel('ForecastImport', 'SprintImport'),
        migrations.RenameModel('ForecastImportRow', 'SprintImportRow'),
        migrations.RenameModel('ForecastReview', 'ImportReview'),
        migrations.RenameModel('ForecastReviewResult', 'ImportReviewResult'),
        migrations.RenameModel('SprintForecastRow', 'SprintConfirmedRow'),
        migrations.RenameModel('SprintForecastReviewComplete', 'SprintImportReviewComplete'),

        # ── Step 2: Add import_type to SprintImport ───────────────────────────
        migrations.AddField(
            model_name='sprintimport',
            name='import_type',
            field=models.CharField(
                choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                default='FORECAST',
                max_length=10,
            ),
        ),

        # ── Step 3: Update unique constraint on SprintImport ──────────────────
        migrations.RemoveConstraint(
            model_name='sprintimport',
            name='unique_forecast_import_version',
        ),
        migrations.AddConstraint(
            model_name='sprintimport',
            constraint=models.UniqueConstraint(
                fields=['sprint', 'team', 'import_type', 'version_number'],
                name='unique_sprint_import_version',
            ),
        ),

        # ── Step 4: Rename FK fields (forecast_import → sprint_import) ────────
        migrations.RenameField('SprintImportRow', 'forecast_import', 'sprint_import'),
        migrations.RenameField('ImportReview', 'forecast_import', 'sprint_import'),
        migrations.RenameField('SprintConfirmedRow', 'forecast_import', 'sprint_import'),
        migrations.RenameField('RechargeDetail', 'forecast_import', 'sprint_import'),

        # ── Step 5: Add import_type to SprintConfirmedRow ─────────────────────
        migrations.AddField(
            model_name='sprintconfirmedrow',
            name='import_type',
            field=models.CharField(
                choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                default='FORECAST',
                max_length=10,
            ),
        ),

        # ── Step 6: SprintImportReviewComplete — change sprint to ForeignKey ──
        # (was OneToOneField; we need (sprint, import_type) uniqueness instead)
        migrations.AlterField(
            model_name='sprintimportreviewcomplete',
            name='sprint',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='import_review_completions',
                to='sprints.sprint',
            ),
        ),

        # ── Step 7: Add import_type to SprintImportReviewComplete ─────────────
        migrations.AddField(
            model_name='sprintimportreviewcomplete',
            name='import_type',
            field=models.CharField(
                choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')],
                default='FORECAST',
                max_length=10,
            ),
        ),

        # ── Step 8: Add (sprint, import_type) unique constraint ───────────────
        migrations.AddConstraint(
            model_name='sprintimportreviewcomplete',
            constraint=models.UniqueConstraint(
                fields=['sprint', 'import_type'],
                name='unique_sprint_import_review_complete',
            ),
        ),
    ]
