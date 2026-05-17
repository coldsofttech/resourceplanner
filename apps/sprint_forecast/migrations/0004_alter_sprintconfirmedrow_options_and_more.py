import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_teams', '0002_deliveryteam_member_count'),
        ('projects', '0013_projectview'),
        ('sprint_forecast', '0003_generic_rename'),
        ('sprints', '0001_initial'),
        ('team_members', '0002_alter_teammember_default_holidays'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # All operations here are related_name / ordering changes only.
        # They are ORM-level metadata and require no database SQL.
        # Using SeparateDatabaseAndState to update Django's migration state
        # without triggering _remake_table on SQLite.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterModelOptions(
                    name='sprintconfirmedrow',
                    options={'ordering': ['sprint', 'team', 'sprint_import', 'id']},
                ),
                migrations.AlterModelOptions(
                    name='sprintimportrow',
                    options={'ordering': ['sprint_import', 'order']},
                ),
                migrations.AlterField(
                    model_name='importreview',
                    name='reviewed_by',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_reviews', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='sprintconfirmedrow',
                    name='assignee',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_confirmed_rows', to='team_members.teammember'),
                ),
                migrations.AlterField(
                    model_name='sprintconfirmedrow',
                    name='label',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_confirmed_rows', to='projects.projectlabel'),
                ),
                migrations.AlterField(
                    model_name='sprintconfirmedrow',
                    name='mapping',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_confirmed_rows', to='sprint_forecast.projectfinancetype'),
                ),
                migrations.AlterField(
                    model_name='sprintconfirmedrow',
                    name='sprint',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='confirmed_rows', to='sprints.sprint'),
                ),
                migrations.AlterField(
                    model_name='sprintconfirmedrow',
                    name='team',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_confirmed_rows', to='delivery_teams.deliveryteam'),
                ),
                migrations.AlterField(
                    model_name='sprintimport',
                    name='imported_by',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sprint_imports', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='sprintimport',
                    name='sprint',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_imports', to='sprints.sprint'),
                ),
                migrations.AlterField(
                    model_name='sprintimport',
                    name='team',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_imports', to='delivery_teams.deliveryteam'),
                ),
                migrations.AlterField(
                    model_name='sprintimportreviewcomplete',
                    name='completed_by',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_review_completions', to=settings.AUTH_USER_MODEL),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='assignee',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_rows', to='team_members.teammember'),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='assignee_override',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_row_overrides', to='team_members.teammember'),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='label',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_rows', to='projects.projectlabel'),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='label_override',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_row_overrides', to='projects.projectlabel'),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='mapping',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_rows', to='sprint_forecast.projectfinancetype'),
                ),
                migrations.AlterField(
                    model_name='sprintimportrow',
                    name='mapping_override',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_row_overrides', to='sprint_forecast.projectfinancetype'),
                ),
            ],
        ),
    ]
