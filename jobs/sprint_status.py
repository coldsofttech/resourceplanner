"""
Sprint Status Job
-----------------
Sets Sprint.is_active based on today's date:
  - Exactly one sprint per financial year whose date window contains today is marked active.
  - All others in the same FY are marked inactive.
  - If today falls between sprints, the most-recently-ended sprint stays active.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


def run() -> dict:
    from apps.sprints.models import Sprint

    today = date.today()
    updated_active = []
    updated_inactive = []

    from apps.financial_years.models import FinancialYear
    for fy in FinancialYear.objects.all():
        sprints = list(Sprint.objects.filter(financial_year=fy).order_by('sprint_number'))
        if not sprints:
            continue

        # Find the sprint whose window contains today
        active_sprint = None
        for s in sprints:
            if s.start_date <= today <= s.end_date:
                active_sprint = s
                break

        # If today is between sprints (gap), keep the last ended sprint active
        if active_sprint is None:
            past = [s for s in sprints if s.end_date < today]
            if past:
                active_sprint = past[-1]

        for s in sprints:
            should_be_active = (active_sprint is not None and s.pk == active_sprint.pk)
            if s.is_active != should_be_active:
                s.is_active = should_be_active
                s.save(update_fields=['is_active'])
                if should_be_active:
                    updated_active.append(s.sprint_name)
                else:
                    updated_inactive.append(s.sprint_name)

    result = {
        'job': 'sprint_status',
        'activated': updated_active,
        'deactivated': updated_inactive,
        'today': str(today),
    }
    logger.info(
        '[sprint_status] activated=%s deactivated=%s',
        len(updated_active), len(updated_inactive),
    )
    return result
