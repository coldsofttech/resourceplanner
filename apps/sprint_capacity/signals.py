"""
Signals that keep SprintCapacity rows in sync with their sources of truth.

Sources that affect capacity:
  1. Sprint         — date window changes → rebuild all members in that sprint.
  2. TeamMember     — member added/changed/removed → rebuild all sprints they overlap.
  3. PublicHoliday  — holiday added/deleted → rebuild affected sprint × member rows.
  4. MemberLeave    — leave changed → rebuild affected sprint × member rows.

The rebuild helper is `SprintCapacityService.regenerate_for_sprint_member()`,
which is cheap for a single cell and can be called in bulk.
"""

import logging

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _cap():
    from .services import SprintCapacityService
    return SprintCapacityService


@receiver(post_save, sender='sprints.Sprint')
def on_sprint_save(sender, instance, **kwargs):
    """Rebuild capacity for all active team members when a sprint changes."""
    try:
        _cap().regenerate_for_sprint(instance)
    except Exception:
        logger.exception("SprintCapacity rebuild failed after Sprint save pk=%s", instance.pk)


@receiver(post_delete, sender='sprints.Sprint')
def on_sprint_delete(sender, instance, **kwargs):
    # SprintCapacity rows are cascade-deleted — nothing extra needed.
    pass


@receiver(post_save, sender='team_members.TeamMember')
def on_team_member_save(sender, instance, **kwargs):
    """Rebuild capacity rows for this member across all overlapping sprints."""
    try:
        _cap().regenerate_for_member(instance)
    except Exception:
        logger.exception(
            "SprintCapacity rebuild failed after TeamMember save pk=%s", instance.pk
        )


@receiver(post_delete, sender='team_members.TeamMember')
def on_team_member_delete(sender, instance, **kwargs):
    # SprintCapacity rows are cascade-deleted — nothing extra needed.
    pass

@receiver(pre_save, sender='public_holidays.PublicHoliday')
def on_holiday_pre_save(sender, instance, **kwargs):
    """Snapshot old date and location before the update is written."""
    if instance.pk is None:
        return  # new record — nothing to snapshot
    try:
        from apps.public_holidays.models import PublicHoliday
        prior = PublicHoliday.objects.only('date', 'location').get(pk=instance.pk)
        instance._old_date     = prior.date
        instance._old_location = prior.location
    except Exception:
        pass  # row vanished between pre_save and now — post_save will handle gracefully


@receiver(post_save, sender='public_holidays.PublicHoliday')
def on_holiday_save(sender, instance, **kwargs):
    """Rebuild capacity for members at the affected location around this date."""
    try:
        old_date = getattr(instance, '_old_date', None)
        old_location = getattr(instance, '_old_location', None)
        _cap().regenerate_for_holiday(instance, old_date=old_date, old_location=old_location)
    except Exception:
        logger.exception(
            "SprintCapacity rebuild failed after PublicHoliday save pk=%s", instance.pk
        )


@receiver(post_delete, sender='public_holidays.PublicHoliday')
def on_holiday_delete(sender, instance, **kwargs):
    try:
        _cap().regenerate_for_holiday(instance)
    except Exception:
        logger.exception(
            "SprintCapacity rebuild failed after PublicHoliday delete pk=%s", instance.pk
        )
