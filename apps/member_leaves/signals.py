import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='public_holidays.PublicHoliday')
def on_holiday_saved(sender, instance, **kwargs):
    """
    Fired after a PublicHoliday is created or updated.
    Recalculate every MemberLeave for members at the same location.
    """
    _recalc(instance.location_id, event='saved')


@receiver(post_delete, sender='public_holidays.PublicHoliday')
def on_holiday_deleted(sender, instance, **kwargs):
    """
    Fired after a PublicHoliday is deleted.
    The holiday is gone, so the day may now count as a working day.
    """
    _recalc(instance.location_id, event='deleted')


def _recalc(location_id, event: str):
    try:
        from .services import MemberLeaveService
        updated = MemberLeaveService.recalculate_for_location(location_id)
        logger.info(
            "Holiday %s for location %s: recalculated %d leave record(s).",
            event, location_id, updated,
        )
    except Exception:
        logger.exception(
            "Error recalculating leaves after holiday %s for location %s.",
            event, location_id,
        )