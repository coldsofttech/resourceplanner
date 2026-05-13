from django.db import migrations


def _deduplicate_placeholder_engineers(apps, schema_editor):
    """
    Before removing `phase` from the unique_together we may have rows that share
    (version_id, team_id, slot_number) with different phase_id values. Keep the
    lowest-pk record per group and re-point any allocation rows to it, then delete
    the duplicates.
    """
    PE  = apps.get_model('resource_plans', 'ResourcePlanPlaceholderEngineer')
    Alloc = apps.get_model('resource_plans', 'ResourcePlanAllocation')

    seen = {}   # (version_id, team_id, slot_number) -> canonical pk
    for pe in PE.objects.order_by('version_id', 'team_id', 'slot_number', 'id'):
        key = (pe.version_id, pe.team_id, pe.slot_number)
        if key not in seen:
            seen[key] = pe.pk
        else:
            # Re-point allocations from duplicate to canonical
            Alloc.objects.filter(placeholder_engineer_id=pe.pk).update(
                placeholder_engineer_id=seen[key]
            )
            pe.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0019_snapshot_models'),
    ]

    operations = [
        migrations.RunPython(_deduplicate_placeholder_engineers, migrations.RunPython.noop),
        # Remove phase from the unique constraint so one engineer slot spans many phases
        migrations.AlterUniqueTogether(
            name='resourceplanplaceholderengineer',
            unique_together={('version', 'team', 'slot_number')},
        ),
    ]
