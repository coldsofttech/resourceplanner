import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='projects.ProjectEstimate')
def on_estimate_saved(sender, instance, **kwargs):
    """Fire approval email when estimate becomes APPROVED and project is already IN_PROGRESS."""
    if instance.status != 'APPROVED' or instance.approval_email_sent:
        return
    if instance.project.status != 'IN_PROGRESS':
        return
    from django.db import transaction
    transaction.on_commit(
        lambda: _try_send_approval_email(instance.project_id, instance.pk)
    )


@receiver(post_save, sender='projects.Project')
def on_project_saved(sender, instance, **kwargs):
    """Fire approval email when project becomes IN_PROGRESS and already has an APPROVED estimate."""
    if instance.status != 'IN_PROGRESS':
        return
    from .models import ProjectEstimate
    approved = (
        ProjectEstimate.objects
        .filter(project=instance, status='APPROVED', approval_email_sent=False)
        .first()
    )
    if not approved:
        return
    from django.db import transaction
    transaction.on_commit(
        lambda: _try_send_approval_email(instance.pk, approved.pk)
    )


def _try_send_approval_email(project_id: int, estimate_id: int) -> None:
    from django.db import transaction
    from .models import Project, ProjectEstimate
    from .email_service import ProjectApprovalEmailService

    try:
        with transaction.atomic():
            try:
                estimate = (
                    ProjectEstimate.objects
                    .select_for_update(nowait=True)
                    .get(pk=estimate_id, status='APPROVED', approval_email_sent=False)
                )
            except ProjectEstimate.DoesNotExist:
                return  # already sent or no longer approved

            project = estimate.project
            if project.status != Project.STATUS_IN_PROGRESS:
                return

            ProjectEstimate.objects.filter(pk=estimate_id).update(approval_email_sent=True)

        ProjectApprovalEmailService.send(project, estimate)

    except Exception as exc:
        logger.exception(
            "Unexpected error sending project approval email for project %s / estimate %s: %s",
            project_id, estimate_id, exc,
        )
