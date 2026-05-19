from django.db import migrations


def seed_monthly_finance_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.get_or_create(
        slug='monthly-finance',
        defaults={
            'name': 'Monthly Finance Report',
            'description': (
                'Aggregated recharge pivot by project and programme for a selected month. '
                'Requires actuals to be confirmed for all sprints in the month before generating.'
            ),
            'report_type': 'STANDARD',
            'is_active': True,
            'sort_order': 4,
        },
    )


def unseed_monthly_finance_report(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.filter(slug='monthly-finance').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0003_kpi_report'),
    ]

    operations = [
        migrations.RunPython(
            seed_monthly_finance_report,
            reverse_code=unseed_monthly_finance_report,
        ),
    ]
