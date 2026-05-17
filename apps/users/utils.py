import logging

logger = logging.getLogger(__name__)


def add_to_guest_group(user) -> None:
    """Add *user* to the GUEST group. Silent no-op if the group doesn't exist yet."""
    from django.contrib.auth.models import Group
    from .apps import GUEST_GROUP_NAME

    try:
        guest_group = Group.objects.get(name=GUEST_GROUP_NAME)
        guest_group.user_set.add(user)
    except Group.DoesNotExist:
        logger.warning(
            "GUEST group not found — could not add user pk=%s to guest group.", user.pk
        )
