import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('delivery_teams', '0001_initial'),
        ('project_types', '0001_initial'),
        ('projects', '0001_initial'),
        ('programmes', '0001_initial'),
        ('sprints', '0001_initial'),
        ('team_members', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectFinanceType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True, validators=[django.core.validators.RegexValidator(message='Code must be UPPER_SNAKE_CASE (e.g. PROJECT, BAU, HOLIDAY).', regex='^[A-Z][A-Z0-9_]*$')], help_text='Unique UPPER_SNAKE_CASE code, e.g. PROJECT, BAU, HOLIDAY.')),
                ('name', models.CharField(max_length=120)),
                ('description', models.CharField(blank=True, max_length=500)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['code']},
        ),
        migrations.CreateModel(
            name='ProjectFinanceTypeMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='finance_type_mappings', to='project_types.projecttype')),
                ('finance_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_type_mappings', to='sprint_forecast.projectfinancetype')),
            ],
            options={'ordering': ['project_type', 'finance_type']},
        ),
        migrations.AddConstraint(
            model_name='projectfinancetypemapping',
            constraint=models.UniqueConstraint(fields=['project_type', 'finance_type'], name='unique_project_finance_type_mapping'),
        ),
        migrations.CreateModel(
            name='ForecastImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('superseded', 'Superseded'), ('confirmed', 'Confirmed')], default='active', max_length=20)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('sprint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forecast_imports', to='sprints.sprint')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forecast_imports', to='delivery_teams.deliveryteam')),
                ('imported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_imports', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['sprint', 'team', 'version_number']},
        ),
        migrations.AddConstraint(
            model_name='forecastimport',
            constraint=models.UniqueConstraint(fields=['sprint', 'team', 'version_number'], name='unique_forecast_import_version'),
        ),
        migrations.CreateModel(
            name='ForecastImportRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('is_manually_added', models.BooleanField(default=False)),
                ('story_type', models.CharField(blank=True, max_length=200)),
                ('jira_id', models.CharField(blank=True, max_length=100)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('assignee_raw', models.CharField(blank=True, max_length=300)),
                ('efforts_ms', models.BigIntegerField(default=0)),
                ('sprint_name', models.CharField(blank=True, max_length=200)),
                ('label_raw', models.CharField(blank=True, max_length=200)),
                ('mapping_raw', models.CharField(blank=True, max_length=100)),
                ('story_type_override', models.CharField(blank=True, max_length=200, null=True)),
                ('jira_id_override', models.CharField(blank=True, max_length=100, null=True)),
                ('title_override', models.CharField(blank=True, max_length=500, null=True)),
                ('assignee_raw_override', models.CharField(blank=True, max_length=300, null=True)),
                ('efforts_ms_override', models.BigIntegerField(blank=True, null=True)),
                ('sprint_name_override', models.CharField(blank=True, max_length=200, null=True)),
                ('forecast_import', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='sprint_forecast.forecastimport')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_rows', to='team_members.teammember')),
                ('assignee_override', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_row_overrides', to='team_members.teammember')),
                ('label', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_rows', to='projects.projectlabel')),
                ('label_override', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_row_overrides', to='projects.projectlabel')),
                ('mapping', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_rows', to='sprint_forecast.projectfinancetype')),
                ('mapping_override', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_row_overrides', to='sprint_forecast.projectfinancetype')),
            ],
            options={'ordering': ['forecast_import', 'order']},
        ),
        migrations.CreateModel(
            name='ForecastReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reviewed_at', models.DateTimeField(auto_now_add=True)),
                ('forecast_import', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='sprint_forecast.forecastimport')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-reviewed_at']},
        ),
        migrations.CreateModel(
            name='ForecastReviewResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_type', models.CharField(choices=[('label_check', 'Label Check'), ('mapping_check', 'Mapping Check'), ('capacity_check', 'Capacity Check')], max_length=30)),
                ('status', models.CharField(choices=[('pass', 'Pass'), ('error', 'Error')], max_length=10)),
                ('message', models.TextField(blank=True)),
                ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='sprint_forecast.forecastreview')),
                ('row', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_results', to='sprint_forecast.forecastimportrow')),
            ],
            options={'ordering': ['review', 'row__order', 'check_type']},
        ),
        migrations.CreateModel(
            name='SprintForecastRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('story_type', models.CharField(blank=True, max_length=200)),
                ('jira_id', models.CharField(blank=True, max_length=100)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('assignee_raw', models.CharField(blank=True, max_length=300)),
                ('efforts_ms', models.BigIntegerField(default=0)),
                ('days', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('sprint_name', models.CharField(blank=True, max_length=200)),
                ('label_raw', models.CharField(blank=True, max_length=200)),
                ('mapping_raw', models.CharField(blank=True, max_length=100)),
                ('is_override', models.BooleanField(default=False)),
                ('sprint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forecast_rows', to='sprints.sprint')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_forecast_rows', to='delivery_teams.deliveryteam')),
                ('forecast_import', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='confirmed_rows', to='sprint_forecast.forecastimport')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_forecast_rows', to='team_members.teammember')),
                ('label', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_forecast_rows', to='projects.projectlabel')),
                ('mapping', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_forecast_rows', to='sprint_forecast.projectfinancetype')),
            ],
            options={'ordering': ['sprint', 'team', 'forecast_import', 'id']},
        ),
        migrations.CreateModel(
            name='SprintForecastReviewComplete',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('override_applied', models.BooleanField(default=False)),
                ('override_notes', models.TextField(blank=True)),
                ('sprint', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='forecast_review_complete', to='sprints.sprint')),
                ('completed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forecast_review_completions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RechargeDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')], default='FORECAST', max_length=10)),
                ('total_days', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sprint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recharge_details', to='sprints.sprint')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recharge_details', to='delivery_teams.deliveryteam')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recharge_details', to='team_members.teammember')),
                ('programme', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='recharge_details', to='programmes.programme')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='recharge_details', to='projects.project')),
                ('label', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recharge_details', to='projects.projectlabel')),
                ('forecast_import', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recharge_details', to='sprint_forecast.forecastimport')),
            ],
            options={'ordering': ['sprint', 'team', 'assignee']},
        ),
        migrations.CreateModel(
            name='Recharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('FORECAST', 'Forecast'), ('ACTUAL', 'Actual')], default='FORECAST', max_length=10)),
                ('total_days', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sprint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recharges', to='sprints.sprint')),
                ('programme', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='recharges', to='programmes.programme')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='recharges', to='projects.project')),
                ('label', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recharges', to='projects.projectlabel')),
                ('finance_contacts', models.ManyToManyField(blank=True, limit_choices_to={'role': 'FINANCE'}, related_name='recharges_as_finance', to='projects.projectcontact')),
                ('project_contacts', models.ManyToManyField(blank=True, limit_choices_to={'role': 'PROJECT'}, related_name='recharges_as_project', to='projects.projectcontact')),
            ],
            options={'ordering': ['sprint', 'type', 'programme', 'project']},
        ),
        migrations.AddConstraint(
            model_name='recharge',
            constraint=models.UniqueConstraint(fields=['sprint', 'type', 'programme', 'project', 'label'], name='unique_recharge_per_sprint_project_label'),
        ),
        migrations.CreateModel(
            name='RechargeStory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jira_id', models.CharField(blank=True, max_length=100)),
                ('title', models.CharField(blank=True, max_length=500)),
                ('total_days', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('recharge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stories', to='sprint_forecast.recharge')),
            ],
            options={'ordering': ['recharge', 'jira_id']},
        ),
    ]
