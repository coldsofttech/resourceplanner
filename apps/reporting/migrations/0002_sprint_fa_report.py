from django.db import migrations


def seed_sprint_fa_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.get_or_create(
        slug='sprint-forecast-actuals',
        defaults={
            'name': 'Sprint Forecast vs. Actuals',
            'description': 'Compare sprint forecast allocations against actuals across all dimensions.',
            'report_type': 'STANDARD',
            'is_active': True,
            'sort_order': 2,
        },
    )


def unseed_sprint_fa_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.filter(slug='sprint-forecast-actuals').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_sprint_fa_report, reverse_code=unseed_sprint_fa_report),
    ]
