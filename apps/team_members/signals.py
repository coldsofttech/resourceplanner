import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import TeamMember

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(pre_save, sender=TeamMember)
def on_member_pre_save(sender, instance, **kwargs):
    """
    Snapshot the current DB state (team + is_active) onto the instance before
    Django writes the new values.  post_save can then compare old vs new to
    decide which teams need their counts refreshed.

    For brand-new instances (no pk yet) there is nothing in the DB to fetch,
    so we skip the query and leave the attributes absent — post_save treats
    missing attributes as "no prior state known" and falls back safely.
    """
    if instance.pk is None:
        return  # new record — nothing to snapshot

    try:
        prior = TeamMember.objects.only('team', 'is_active').get(pk=instance.pk)
        instance._original_team = prior.team
        instance._original_is_active = prior.is_active
    except TeamMember.DoesNotExist:
        pass  # row was deleted between pre_save and now — nothing to snapshot


def _sync_team_count(team) -> None:
    """
    Recount active members for *team* and persist only the member_count column.

    Uses update_fields so that:
    - The team's updated_at (auto_now) is NOT touched — this is a housekeeping
      write, not a user-initiated change.
    - No other signals are triggered on DeliveryTeam.
    - The write is a single UPDATE … SET member_count = N WHERE id = X.
    """
    if team is None:
        return

    count = TeamMember.objects.filter(team=team, is_active=True).count()

    # Import here to avoid circular imports at module load time.
    from apps.delivery_teams.models import DeliveryTeam
    try:
        DeliveryTeam.objects.filter(pk=team.pk).update(member_count=count)
    except Exception:
        logger.exception(
            "Failed to sync member_count for team '%s' (pk=%s)", team, team.pk
        )


@receiver(post_save, sender=TeamMember)
def on_member_save(sender, instance, **kwargs):
    """
    Fires after a TeamMember is created or updated.

    We must handle two cases:
    1. The member's team changed (reassignment). Both the old team and the new
       team need their counts updated.
    2. The member's is_active flag changed. Only the current team is affected.

    Django doesn't give us the pre-save state in post_save, so we compare
    against the value stored in instance.__original_team and
    instance.__original_is_active, which are injected by the pre_save signal
    below. If those attributes are absent (e.g. during fixtures/tests) we fall
    back to syncing only the current team.
    """
    current_team = instance.team

    original_team = getattr(instance, '_original_team', current_team)
    original_is_active = getattr(instance, '_original_is_active', instance.is_active)

    teams_to_sync = set()

    # Team changed — old team loses a member, new team gains one.
    if original_team != current_team:
        teams_to_sync.add(original_team)
        teams_to_sync.add(current_team)
    else:
        # is_active toggled, or any other field changed — refresh current team.
        if original_is_active != instance.is_active or current_team is not None:
            teams_to_sync.add(current_team)

    for team in teams_to_sync:
        _sync_team_count(team)


@receiver(post_delete, sender=TeamMember)
def on_member_delete(sender, instance, **kwargs):
    """
    Fires after a TeamMember row is hard-deleted.
    Sync whichever team the member belonged to.
    """
    _sync_team_count(instance.team)


# ---------------------------------------------------------------------------
# User ↔ TeamMember email-based linking
# ---------------------------------------------------------------------------

def _sync_member_user_link(member):
    """
    Look up a User whose email matches the member's email_address (case-insensitive)
    and store the FK on the member row.  Uses queryset.update() so no further
    signals are fired and no other fields are touched.
    """
    try:
        matched_user = User.objects.get(email__iexact=member.email_address)
    except User.DoesNotExist:
        matched_user = None
    except User.MultipleObjectsReturned:
        logger.warning(
            "Multiple users share email '%s' — skipping auto-link for TeamMember pk=%s.",
            member.email_address, member.pk,
        )
        return

    current_user_id = member.user_id

    if matched_user is not None:
        if current_user_id != matched_user.pk:
            # Before claiming, make sure no other member already holds this user.
            conflict = (
                TeamMember.objects
                .filter(user=matched_user)
                .exclude(pk=member.pk)
                .exists()
            )
            if conflict:
                logger.warning(
                    "User pk=%s is already linked to another TeamMember — "
                    "skipping auto-link for TeamMember pk=%s.",
                    matched_user.pk, member.pk,
                )
                return
            TeamMember.objects.filter(pk=member.pk).update(user=matched_user)
    else:
        if current_user_id is not None:
            TeamMember.objects.filter(pk=member.pk).update(user=None)


@receiver(post_save, sender=TeamMember)
def on_member_save_link_user(sender, instance, **kwargs):
    """
    After a TeamMember is saved, attempt to resolve the linked user by email.
    Only runs when email_address was created or changed.
    """
    update_fields = kwargs.get('update_fields')

    # Skip if update_fields is set and 'email_address' is not among them
    # (e.g. the team-count sync writes only 'user', so we must also skip that).
    if update_fields is not None and 'email_address' not in update_fields:
        return

    _sync_member_user_link(instance)


@receiver(post_save, sender=User)
def on_user_save_link_member(sender, instance, **kwargs):
    """
    After a User is saved (or their email changes), find any TeamMember whose
    email_address matches and update the FK so the link stays consistent.
    """
    update_fields = kwargs.get('update_fields')

    # Only care about changes that touch the email.
    if update_fields is not None and 'email' not in update_fields:
        return

    try:
        member = TeamMember.objects.get(email_address__iexact=instance.email)
    except TeamMember.DoesNotExist:
        return
    except TeamMember.MultipleObjectsReturned:
        logger.warning(
            "Multiple TeamMembers share email '%s' — skipping auto-link for User pk=%s.",
            instance.email, instance.pk,
        )
        return

    if member.user_id != instance.pk:
        conflict = (
            TeamMember.objects
            .filter(user=instance)
            .exclude(pk=member.pk)
            .exists()
        )
        if not conflict:
            TeamMember.objects.filter(pk=member.pk).update(user=instance)