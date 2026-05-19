import logging

from django.contrib.auth import get_user_model
from django.db import DatabaseError

from .models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:

    @staticmethod
    def create(user, title, notification_type, body='', link=''):
        """Create a single in-app notification for one user."""
        try:
            return Notification.objects.create(
                user=user,
                title=title,
                body=body,
                link=link,
                notification_type=notification_type,
            )
        except DatabaseError:
            logger.exception('Failed to create notification for user %s', user.pk)
            return None

    @staticmethod
    def create_for_emails(emails, title, notification_type, body='', link=''):
        """
        Create notifications for all system users whose email matches one of the
        provided addresses. Silently skips addresses not found in the system.
        """
        if not emails:
            return
        users = User.objects.filter(email__in=emails, is_active=True)
        for user in users:
            NotificationService.create(user, title, notification_type, body=body, link=link)

    @staticmethod
    def mark_read(notification_id, user):
        Notification.objects.filter(pk=notification_id, user=user).update(is_read=True)

    @staticmethod
    def dismiss(notification_id, user):
        Notification.objects.filter(pk=notification_id, user=user).update(is_dismissed=True)

    @staticmethod
    def mark_all_read(user):
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)

    @staticmethod
    def list_for_user(user, page=1, page_size=20, include_dismissed=False):
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        qs = Notification.objects.filter(user=user)
        if not include_dismissed:
            qs = qs.filter(is_dismissed=False)
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        return {
            'results': list(page_obj.object_list),
            'unread_count': qs.filter(is_read=False).count(),
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
        }
