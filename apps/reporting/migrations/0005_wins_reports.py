from django.db import migrations


def seed_wins_reports(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.get_or_create(
        slug='weekly-wins',
        defaults={
            'name': 'Weekly Wins Report',
            'description': (
                'View all team wins for a selected week or date range. '
                'Tabular output with per-team win counts and print-friendly layout.'
            ),
            'report_type': 'STANDARD',
            'is_active': True,
            'sort_order': 10,
        },
    )
    Report.objects.get_or_create(
        slug='monthly-wins',
        defaults={
            'name': 'Monthly Wins Report',
            'description': (
                'Phase 1 and Phase 2 survey results, nominations, and declared winners '
                'for a selected Monthly Win.'
            ),
            'report_type': 'STANDARD',
            'is_active': True,
            'sort_order': 11,
        },
    )


def unseed_wins_reports(apps, schema_editor):
    Report = apps.get_model('reporting', 'Report')
    Report.objects.filter(slug__in=['weekly-wins', 'monthly-wins']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0004_monthly_finance_report'),
    ]

    operations = [
        migrations.RunPython(
            seed_wins_reports,
            reverse_code=unseed_wins_reports,
        ),
    ]
