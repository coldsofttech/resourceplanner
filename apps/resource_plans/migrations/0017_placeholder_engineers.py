from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0016_phase9_conflicts'),
        ('delivery_teams', '0002_deliveryteam_member_count'),
        ('sprints', '0001_initial'),
        ('team_members', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlaceholderEngineer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence_number', models.PositiveIntegerField()),
                ('display_name', models.CharField(max_length=50)),
                ('capacity_days_per_sprint', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('replaced_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('version', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='hire_placeholders',
                    to='resource_plans.resourceplanversion',
                )),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='+',
                    to='delivery_teams.deliveryteam',
                )),
                ('manpower_request', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='placeholder_engineers',
                    to='resource_plans.manpowerrequest',
                )),
                ('onboard_sprint', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='+',
                    to='sprints.sprint',
                )),
                ('engine_suggested_sprint', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='sprints.sprint',
                )),
                ('replaced_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='team_members.teammember',
                )),
            ],
            options={'ordering': ['sequence_number']},
        ),
        migrations.AddConstraint(
            model_name='placeholderengineer',
            constraint=models.UniqueConstraint(fields=['version', 'sequence_number'], name='unique_ph_version_seq'),
        ),
        migrations.CreateModel(
            name='PlaceholderEngineerAbsence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('days', models.DecimalField(decimal_places=2, default=0, max_digits=4)),
                ('is_engine_generated', models.BooleanField(default=True)),
                ('override_days', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ('override_notes', models.TextField(blank=True, null=True)),
                ('placeholder_engineer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='absences',
                    to='resource_plans.placeholderengineer',
                )),
                ('sprint', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='+',
                    to='sprints.sprint',
                )),
            ],
            options={'ordering': ['sprint__sprint_number']},
        ),
        migrations.AddConstraint(
            model_name='placeholderengineerabsence',
            constraint=models.UniqueConstraint(fields=['placeholder_engineer', 'sprint'], name='unique_ph_absence_sprint'),
        ),
    ]
