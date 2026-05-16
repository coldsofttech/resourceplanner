import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

STANDARD_REPORTS = [
    {
        "slug": "demand-capacity",
        "name": "Demand & Capacity",
        "description": (
            "Shows allocated demand versus available capacity across programme "
            "categories and sprints for a resource plan version."
        ),
        "sort_order": 1,
    },
]


def seed_standard_reports(sender, **kwargs):
    try:
        from .models import Report

        for entry in STANDARD_REPORTS:
            Report.objects.update_or_create(
                slug=entry["slug"],
                defaults={
                    "name": entry["name"],
                    "description": entry["description"],
                    "report_type": Report.STANDARD,
                    "is_active": True,
                    "sort_order": entry["sort_order"],
                },
            )
    except Exception as exc:
        logger.warning("Reporting seed skipped (tables may not exist yet): %s", exc)


class ReportingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reporting"
    verbose_name = "Reporting"

    def ready(self):
        from django.db.models.signals import post_migrate

        post_migrate.connect(seed_standard_reports, sender=self)
