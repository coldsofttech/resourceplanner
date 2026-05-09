from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("resource_plans", "0007_remove_sprint_point_price"),
        ("sprints", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanPhase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("sequence_order", models.PositiveIntegerField(default=1)),
                ("max_days_per_sprint", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("ramp_pattern", models.CharField(
                    choices=[
                        ("FLAT", "Flat"), ("RAMP_UP", "Ramp Up"), ("RAMP_DOWN", "Ramp Down"),
                        ("RAMP_UP_DOWN", "Ramp Up/Down"), ("RAMP_UP_STEADY", "Ramp Up then Steady"),
                        ("STEADY_DOWN", "Steady then Down"), ("STEPPED", "Stepped"), ("CUSTOM", "Custom"),
                    ],
                    default="FLAT",
                    max_length=20,
                )),
                ("allow_multiple_engineers", models.BooleanField(default=False)),
                ("split_mode", models.CharField(
                    choices=[("PERCENT", "Percent"), ("DAYS", "Days"), ("EQUAL", "Equal"), ("AUTO", "Auto")],
                    default="AUTO",
                    max_length=10,
                )),
                ("is_split_incomplete", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True, null=True)),
                ("plan_project_team", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="phases",
                    to="resource_plans.resourceplanversionprojectteam",
                )),
                ("start_sprint", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="sprints.sprint",
                )),
                ("end_sprint", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="sprints.sprint",
                )),
            ],
            options={"ordering": ["sequence_order"]},
        ),
        migrations.CreateModel(
            name="PlanPhaseSegment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("segment_order", models.PositiveIntegerField()),
                ("segment_type", models.CharField(
                    choices=[("RAMP", "Ramp"), ("FLAT", "Flat")],
                    max_length=10,
                )),
                ("start_pct", models.DecimalField(decimal_places=2, max_digits=5)),
                ("end_pct", models.DecimalField(decimal_places=2, max_digits=5)),
                ("progression", models.CharField(
                    choices=[
                        ("LINEAR", "Linear"), ("EXPONENTIAL", "Exponential"),
                        ("LOGARITHMIC", "Logarithmic"), ("STEPPED", "Stepped"), ("FLAT", "Flat"),
                    ],
                    default="LINEAR",
                    max_length=20,
                )),
                ("duration", models.PositiveIntegerField()),
                ("step_count", models.PositiveIntegerField(blank=True, null=True)),
                ("phase", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="segments",
                    to="resource_plans.planphase",
                )),
            ],
            options={"ordering": ["segment_order"]},
        ),
        migrations.AddConstraint(
            model_name="planphasesegment",
            constraint=models.UniqueConstraint(fields=["phase", "segment_order"], name="unique_phase_segment_order"),
        ),
        migrations.AlterUniqueTogether(
            name="planphasesegment",
            unique_together={("phase", "segment_order")},
        ),
        migrations.CreateModel(
            name="PlanPhaseDependency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dependency_type", models.CharField(
                    choices=[
                        ("SS", "Start-to-Start"), ("FS", "Finish-to-Start"),
                        ("FF", "Finish-to-Finish"), ("SF", "Start-to-Finish"),
                    ],
                    max_length=2,
                )),
                ("lag_sprints", models.IntegerField(default=0)),
                ("phase", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="dependencies",
                    to="resource_plans.planphase",
                )),
                ("predecessor_phase", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="successor_dependencies",
                    to="resource_plans.planphase",
                )),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AlterUniqueTogether(
            name="planphasedependency",
            unique_together={("phase", "predecessor_phase")},
        ),
        migrations.CreateModel(
            name="PlanPhasePause",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("input_mode", models.CharField(
                    choices=[("SPRINT", "Sprint"), ("COUNT", "Count")],
                    max_length=10,
                )),
                ("pause_sprint_count", models.PositiveIntegerField(blank=True, null=True)),
                ("is_beyond_fy", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True, null=True)),
                ("phase", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="pauses",
                    to="resource_plans.planphase",
                )),
                ("pause_from", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="sprints.sprint",
                )),
                ("pause_until_sprint", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="sprints.sprint",
                )),
                ("resume_sprint", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="sprints.sprint",
                )),
            ],
            options={"ordering": ["pause_from__sprint_number"]},
        ),
        migrations.AlterUniqueTogether(
            name="planphasepause",
            unique_together={("phase", "pause_from")},
        ),
    ]
