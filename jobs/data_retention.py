"""
Data Retention Job
------------------
Deletes records older than DATA_RETENTION_YEARS (default 7) from history/audit tables,
comments, notifications, and closed/cancelled items.

Safe to run repeatedly — uses Django ORM bulk deletes with explicit cutoff dates.
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Tables and their cutoff field — (ModelClass, field_name)
# Imported lazily inside run() so Django is already set up.
def _get_targets():
    from apps.projects.models import (
        ProjectStatusHistory,
        ProjectEstimateHistory,
        ProjectBudgetHistory,
        ProjectContactHistory,
        ProjectComment,
        ProjectCommentAttachment,
    )
    from apps.notifications.models import Notification
    from apps.resource_plans.models import ResourcePlanComment

    return [
        # History / audit tables
        (ProjectStatusHistory,    'created_at'),
        (ProjectEstimateHistory,  'created_at'),
        (ProjectBudgetHistory,    'created_at'),
        (ProjectContactHistory,   'created_at'),
        # Comments
        (ProjectComment,          'created_at'),
        (ProjectCommentAttachment,'created_at'),
        (ResourcePlanComment,     'created_at'),
        # Notifications
        (Notification,            'created_at'),
    ]


def run() -> dict:
    from apps.configurations.services import ConfigurationService

    years = ConfigurationService.get_int('DATA_RETENTION_YEARS', 7)
    # Build cutoff as a date then convert so it works with DateTimeField comparisons
    from django.utils import timezone
    import datetime
    cutoff_date = date.today() - datetime.timedelta(days=years * 365)
    cutoff = timezone.make_aware(
        datetime.datetime.combine(cutoff_date, datetime.time.min)
    )

    summary = {'job': 'data_retention', 'retention_years': years, 'cutoff': str(cutoff_date), 'deleted': {}}

    for model_cls, field in _get_targets():
        table = model_cls.__name__
        try:
            qs = model_cls.objects.filter(**{f'{field}__lt': cutoff})
            count, _ = qs.delete()
            summary['deleted'][table] = count
            if count:
                logger.info('[data_retention] %s: deleted %d records older than %s', table, count, cutoff_date)
        except Exception as exc:
            logger.error('[data_retention] %s: failed — %s', table, exc)
            summary['deleted'][table] = f'ERROR: {exc}'

    total = sum(v for v in summary['deleted'].values() if isinstance(v, int))
    logger.info('[data_retention] total deleted: %d (cutoff: %s)', total, cutoff_date)
    summary['total_deleted'] = total
    return summary
