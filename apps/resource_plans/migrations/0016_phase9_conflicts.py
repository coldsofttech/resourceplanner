from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0015_remove_resourceplanplaceholderengineer_unique_placeholder_slot_and_more'),
        ('delivery_teams', '0002_deliveryteam_member_count'),
        ('projects', '0001_initial'),
        ('sprints', '0001_initial'),
        ('team_members', '0001_initial'),
    ]

    operations = [
        # ResourcePlanVersion.has_allocation_overrides
        migrations.AddField(
            model_name='resourceplanversion',
            name='has_allocation_overrides',
            field=models.BooleanField(default=False),
        ),
        # PlanPhase.days_effort
        migrations.AddField(
            model_name='planphase',
            name='days_effort',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Override: total days this phase should consume (overrides team total ÷ n_phases).',
                max_digits=8,
                null=True,
            ),
        ),
        # Conflict model
        migrations.CreateModel(
            name='Conflict',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conflict_type', models.CharField(
                    choices=[
                        ('CAPACITY_EXCEEDED', 'Capacity Exceeded'),
                        ('COMPETING_PRIORITY', 'Competing Priority'),
                        ('TIMELINE_BREACH', 'Timeline Breach'),
                        ('BUDGET_EXCEEDED', 'Budget Exceeded'),
                        ('DEPENDENCY_VIOLATED', 'Dependency Violated'),
                        ('UNRESOLVABLE_GAP', 'Unresolvable Gap'),
                        ('THRESHOLD_BREACH', 'Threshold Breach'),
                    ],
                    max_length=30,
                )),
                ('severity', models.CharField(
                    choices=[('ERROR', 'Error'), ('WARNING', 'Warning'), ('INFO', 'Info')],
                    default='ERROR',
                    max_length=10,
                )),
                ('status', models.CharField(
                    choices=[('OPEN', 'Open'), ('RESOLVED', 'Resolved'), ('DISMISSED', 'Dismissed')],
                    default='OPEN',
                    max_length=20,
                )),
                ('description', models.TextField()),
                ('engine_data', models.JSONField(default=dict)),
                ('resolution_type', models.CharField(
                    blank=True,
                    choices=[
                        ('DEPRIORITISED', 'Deprioritised'),
                        ('TIMELINE_SHIFTED', 'Timeline Shifted'),
                        ('ENGINEER_SWAPPED', 'Engineer Swapped'),
                        ('TEAM_CHANGED', 'Team Changed'),
                        ('MANPOWER_RAISED', 'Manpower Raised'),
                        ('REBALANCED', 'Rebalanced'),
                        ('DISMISSED', 'Dismissed'),
                    ],
                    max_length=30,
                    null=True,
                )),
                ('resolution_notes', models.TextField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('allocation_set', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='conflicts',
                    to='resource_plans.resourceplanallocationset',
                )),
                ('engine_job', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='conflicts',
                    to='resource_plans.planenginejob',
                )),
                ('affected_project', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='projects.project',
                )),
                ('affected_phase', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='conflicts',
                    to='resource_plans.planphase',
                )),
                ('affected_team_member', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='team_members.teammember',
                )),
                ('affected_sprint', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='sprints.sprint',
                )),
                ('affected_team', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to='delivery_teams.deliveryteam',
                )),
            ],
            options={'ordering': ['status', 'severity', 'conflict_type', '-created_at']},
        ),
        # ManpowerRequest model
        migrations.CreateModel(
            name='ManpowerRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sprints_needed', models.PositiveIntegerField()),
                ('days_needed', models.DecimalField(decimal_places=2, max_digits=6)),
                ('status', models.CharField(
                    choices=[
                        ('OPEN', 'Open'),
                        ('HIRING', 'Hiring'),
                        ('REBALANCED', 'Rebalanced'),
                        ('DISMISSED', 'Dismissed'),
                    ],
                    default='OPEN',
                    max_length=20,
                )),
                ('resolution_notes', models.TextField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('allocation_set', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='manpower_requests',
                    to='resource_plans.resourceplanallocationset',
                )),
                ('conflict', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='manpower_requests',
                    to='resource_plans.conflict',
                )),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='+',
                    to='delivery_teams.deliveryteam',
                )),
                ('phase', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='manpower_requests',
                    to='resource_plans.planphase',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
