import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import TeamMember, TeamMemberAssignment

logger = logging.getLogger(__name__)

User = get_user_model()


# ---------------------------------------------------------------------------
# member_count sync — driven by TeamMemberAssignment changes
# ---------------------------------------------------------------------------

def _sync_team_count(team) -> None:
    """
    Recount active, assignable-role members for *team* and persist only the
    member_count column.

    Uses update_fields so that:
    - The team's updated_at (auto_now) is NOT touched.
    - No other signals are triggered on DeliveryTeam.
    - The write is a single UPDATE … SET member_count = N WHERE id = X.
    """
    if team is None:
        return

    count = TeamMemberAssignment.objects.filter(
        team=team,
        member__is_active=True,
        member__role__is_assignable=True,
    ).count()

    from apps.delivery_teams.models import DeliveryTeam
    try:
        DeliveryTeam.objects.filter(pk=team.pk).update(member_count=count)
    except Exception:
        logger.exception(
            "Failed to sync member_count for team '%s' (pk=%s)", team, team.pk
        )


@receiver(post_save, sender=TeamMemberAssignment)
def on_assignment_save(sender, instance, created, **kwargs):
    """Fires after a team assignment is created. Sync the affected team's count."""
    if created:
        _sync_team_count(instance.team)


@receiver(post_delete, sender=TeamMemberAssignment)
def on_assignment_delete(sender, instance, **kwargs):
    """
    Fires after a team assignment is removed (including cascades from member delete).
    Sync the affected team's count.
    """
    _sync_team_count(instance.team)


@receiver(pre_save, sender=TeamMember)
def on_member_pre_save(sender, instance, **kwargs):
    """
    Snapshot is_active and role_id before save so post_save can detect changes.
    """
    if instance.pk is None:
        return
    try:
        prior = TeamMember.objects.only('is_active', 'role_id').get(pk=instance.pk)
        instance._original_is_active = prior.is_active
        instance._original_role_id = prior.role_id
    except TeamMember.DoesNotExist:
        pass


@receiver(post_save, sender=TeamMember)
def on_member_save(sender, instance, **kwargs):
    """
    Fires after a TeamMember is saved.
    When is_active or role changes, re-sync counts for all teams this member
    is assigned to (only assignable-role members affect member_count).
    """
    update_fields = kwargs.get('update_fields')

    # Skip if this save only touched user/email fields (internal link sync).
    relevant_fields = {'is_active', 'role', 'role_id'}
    if update_fields is not None and not relevant_fields.intersection(update_fields):
        return

    original_is_active = getattr(instance, '_original_is_active', instance.is_active)
    original_role_id = getattr(instance, '_original_role_id', instance.role_id)

    is_active_changed = original_is_active != instance.is_active
    role_changed = original_role_id != instance.role_id

    if not is_active_changed and not role_changed:
        return

    # Sync all teams where this member has assignments that could affect counts.
    for assignment in TeamMemberAssignment.objects.filter(
        member=instance
    ).select_related('team'):
        _sync_team_count(assignment.team)


# ---------------------------------------------------------------------------
# User ↔ TeamMember email-based linking
# ---------------------------------------------------------------------------

def _sync_member_user_link(member):
    """
    Look up a User whose email matches the member's email_address (case-insensitive)
    and store the FK on the member row.
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


@receiver(post_save, sender=User)
def on_user_save_sync_member_name(sender, instance, **kwargs):
    """
    When a User's first_name or last_name is updated, keep the linked TeamMember's
    stored name fields and display_name in sync.
    """
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        if 'first_name' not in update_fields and 'last_name' not in update_fields:
            return

    first = instance.first_name or ''
    last = instance.last_name or ''
    new_display = f"{last.strip()}, {first.strip()}" if last.strip() and first.strip() else (last or first).strip()

    TeamMember.objects.filter(user=instance).update(
        first_name=first,
        last_name=last,
        display_name=new_display,
    )
