from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("resource_plans", "0008_phase_configuration"),
        ("team_members", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("auto_assign", models.BooleanField(default=False)),
                ("assignment_type", models.CharField(
                    choices=[
                        ("ENGINEER", "Engineer"),
                        ("ARCHITECT", "Architect"),
                        ("ADHOC", "Ad-hoc"),
                        ("INTERIM", "Interim"),
                    ],
                    default="ENGINEER",
                    max_length=20,
                )),
                ("interim_sprint_count", models.PositiveIntegerField(blank=True, null=True)),
                ("split_value", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("includes_in_budget", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("phase", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="assignments",
                    to="resource_plans.planphase",
                )),
                ("team_member", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="team_members.teammember",
                )),
                ("replaces_member", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="team_members.teammember",
                )),
            ],
            options={
                "ordering": ["id"],
            },
        ),
    ]
