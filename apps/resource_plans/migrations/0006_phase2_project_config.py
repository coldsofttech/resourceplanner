import decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_teams', '0002_deliveryteam_member_count'),
        ('projects', '0013_projectview'),
        ('resource_plans', '0005_resourceplancomment'),
        ('sprints', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourceplanversion',
            name='sprint_point_price',
            field=models.DecimalField(decimal_places=2, default=decimal.Decimal('1000.00'), max_digits=10),
        ),
        migrations.CreateModel(
            name='ResourcePlanVersionProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('basis', models.CharField(choices=[('BUDGET', 'Budget'), ('ESTIMATE', 'Estimate'), ('CUSTOM', 'Custom')], max_length=20)),
                ('basis_amount', models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ('basis_synced_at', models.DateTimeField(blank=True, null=True)),
                ('days_required', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('is_over_threshold', models.BooleanField(default=False)),
                ('is_under_threshold', models.BooleanField(default=False)),
                ('is_team_budget_mismatch', models.BooleanField(default=False)),
                ('is_percent_incomplete', models.BooleanField(default=False)),
                ('priority_snapshot', models.CharField(blank=True, max_length=20, null=True)),
                ('priority_override', models.CharField(blank=True, max_length=20, null=True)),
                ('confidence_snapshot', models.CharField(blank=True, max_length=20, null=True)),
                ('confidence_override', models.CharField(blank=True, max_length=20, null=True)),
                ('dates_strict', models.BooleanField(default=False)),
                ('budget_release_mode', models.CharField(blank=True, choices=[('SPRINT', 'Sprint'), ('MONTH', 'Month')], max_length=10, null=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('end_sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='sprints.sprint')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='resource_plan_version_projects', to='projects.project')),
                ('snapshotted_budget', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='projects.projectbudget')),
                ('snapshotted_estimate', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='projects.projectestimate')),
                ('start_sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='sprints.sprint')),
                ('version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='resource_plans.resourceplanversion')),
            ],
            options={
                'ordering': ['display_order', 'created_at'],
                'unique_together': {('version', 'project')},
            },
        ),
        migrations.CreateModel(
            name='ResourcePlanVersionProjectTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allocation_type', models.CharField(choices=[('PERCENT', 'Percent'), ('DAYS', 'Days'), ('BUDGET', 'Budget')], max_length=20)),
                ('allocation_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('allocation_days', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('allocation_budget', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('allocated_days', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('sequence_order', models.PositiveIntegerField(default=1)),
                ('plan_project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teams', to='resource_plans.resourceplanversionproject')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='delivery_teams.deliveryteam')),
            ],
            options={
                'ordering': ['sequence_order', 'team__name'],
                'unique_together': {('plan_project', 'team')},
            },
        ),
        migrations.CreateModel(
            name='ResourcePlanVersionProjectBudgetRelease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_type', models.CharField(choices=[('SPRINT', 'Sprint'), ('MONTH', 'Month')], max_length=10)),
                ('month', models.CharField(blank=True, max_length=3, null=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('notes', models.TextField(blank=True, null=True)),
                ('plan_project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='budget_releases', to='resource_plans.resourceplanversionproject')),
                ('sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='sprints.sprint')),
            ],
            options={
                'ordering': ['entry_type', 'sprint__sprint_number', 'month'],
            },
        ),
    ]
