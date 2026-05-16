from django.db import migrations, models


def clear_recharges(apps, schema_editor):
    # Existing rows are keyed by (sprint, type, programme, project, label).
    # Dropping label would produce duplicates, so wipe and let Review Complete rebuild them.
    Recharge = apps.get_model('sprint_forecast', 'Recharge')
    Recharge.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0001_initial'),
    ]

    operations = [
        # Clear data that would violate the new (narrower) unique constraint
        migrations.RunPython(clear_recharges, migrations.RunPython.noop),
        # Drop old unique constraint that included label
        migrations.RemoveConstraint(
            model_name='recharge',
            name='unique_recharge_per_sprint_project_label',
        ),
        # Remove the label FK column
        migrations.RemoveField(
            model_name='recharge',
            name='label',
        ),
        # Add new unique constraint without label
        migrations.AddConstraint(
            model_name='recharge',
            constraint=models.UniqueConstraint(
                fields=['sprint', 'type', 'programme', 'project'],
                name='unique_recharge_per_sprint_project',
            ),
        ),
    ]
