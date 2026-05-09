from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("resource_plans", "0006_phase2_project_config"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="resourceplanversion",
            name="sprint_point_price",
        ),
    ]
