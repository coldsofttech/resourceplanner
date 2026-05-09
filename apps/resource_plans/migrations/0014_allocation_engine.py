from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("delivery_teams", "0001_initial"),
        ("programmes", "0001_initial"),
        ("projects", "0001_initial"),
        ("sprints", "0001_initial"),
        ("team_members", "0001_initial"),
        ("resource_plans", "0013_engine_overrides"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResourcePlanPlaceholderEngineer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slot_number", models.PositiveIntegerField(default=1)),
                ("name", models.CharField(max_length=100)),
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
                ("version", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="placeholder_engineers",
                    to="resource_plans.resourceplanversion",
                )),
                ("team", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="delivery_teams.deliveryteam",
                )),
                ("phase", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="placeholder_engineers",
                    to="resource_plans.planphase",
                )),
            ],
            options={
                "ordering": ["team__name", "slot_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="resourceplanplaceholderengineer",
            constraint=models.UniqueConstraint(
                fields=["version", "team", "phase", "slot_number"],
                name="unique_placeholder_slot",
            ),
        ),
        migrations.CreateModel(
            name="ResourcePlanAllocationSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(
                    choices=[
                        ("DRAFT", "Draft"),
                        ("ACTIVE", "Active"),
                        ("SUPERSEDED", "Superseded"),
                    ],
                    default="DRAFT",
                    max_length=20,
                )),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("version", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="allocation_sets",
                    to="resource_plans.resourceplanversion",
                )),
                ("engine_job", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="allocation_sets",
                    to="resource_plans.planenginejob",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ResourcePlanAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assignment_type", models.CharField(
                    choices=[
                        ("ENGINEER", "Engineer"),
                        ("ARCHITECT", "Architect"),
                        ("ADHOC", "Ad-hoc"),
                        ("INTERIM", "Interim"),
                    ],
                    max_length=20,
                )),
                ("includes_in_budget", models.BooleanField(default=True)),
                ("engine_days", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("override_days", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("override_notes", models.TextField(blank=True, null=True)),
                ("overridden_at", models.DateTimeField(blank=True, null=True)),
                ("allocation_set", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="allocations",
                    to="resource_plans.resourceplanallocationset",
                )),
                ("programme", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="programmes.programme",
                )),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="projects.project",
                )),
                ("team", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="delivery_teams.deliveryteam",
                )),
                ("team_member", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="team_members.teammember",
                )),
                ("placeholder_engineer", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="resource_plans.resourceplanplaceholderengineer",
                )),
                ("sprint", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="sprints.sprint",
                )),
                ("phase", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="resource_plans.planphase",
                )),
                ("assignment", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="resource_plans.planassignment",
                )),
            ],
            options={
                "ordering": ["sprint__sprint_number"],
            },
        ),
    ]
