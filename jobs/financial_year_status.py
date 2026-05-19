"""
Financial Year Status Job
-------------------------
Sets FinancialYear.is_active based on today's date:
  - The FY whose window contains today is marked active.
  - All others are marked inactive.
  - At most one FY is ever active at a time.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


def run() -> dict:
    from apps.financial_years.models import FinancialYear

    today = date.today()
    activated = []
    deactivated = []

    for fy in FinancialYear.objects.all():
        should_be_active = fy.start_date <= today <= fy.end_date
        if fy.is_active != should_be_active:
            fy.is_active = should_be_active
            fy.save(update_fields=['is_active'])
            if should_be_active:
                activated.append(str(fy))
            else:
                deactivated.append(str(fy))

    result = {
        'job': 'financial_year_status',
        'activated': activated,
        'deactivated': deactivated,
        'today': str(today),
    }
    logger.info(
        '[financial_year_status] activated=%s deactivated=%s',
        activated, deactivated,
    )
    return result
