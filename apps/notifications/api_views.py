import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService

logger = logging.getLogger(__name__)


class NotificationListView(APIView):
    """GET  /api/v1/notifications/  — list undismissed notifications for the current user."""

    def get(self, request):
        page      = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        include_dismissed = request.query_params.get('dismissed', '').lower() == 'true'

        data = NotificationService.list_for_user(
            request.user,
            page=page,
            page_size=page_size,
            include_dismissed=include_dismissed,
        )
        serialized = NotificationSerializer(data['results'], many=True).data
        return Response({
            'results':      serialized,
            'unread_count': data['unread_count'],
            'total_count':  data['total_count'],
            'total_pages':  data['total_pages'],
            'current_page': data['current_page'],
        })


class NotificationDetailView(APIView):
    """PATCH /api/v1/notifications/{id}/  — mark read or dismiss."""

    def patch(self, request, pk):
        try:
            n = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if 'is_read' in request.data:
            n.is_read = bool(request.data['is_read'])
        if 'is_dismissed' in request.data:
            n.is_dismissed = bool(request.data['is_dismissed'])
        n.save(update_fields=['is_read', 'is_dismissed'])
        return Response(NotificationSerializer(n).data)


class NotificationMarkAllReadView(APIView):
    """POST /api/v1/notifications/mark-all-read/  — mark all as read."""

    def post(self, request):
        NotificationService.mark_all_read(request.user)
        return Response({'detail': 'All notifications marked as read.'})


class NotificationUnreadCountView(APIView):
    """GET /api/v1/notifications/unread-count/ — lightweight count for polling."""

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False, is_dismissed=False
        ).count()
        return Response({'unread_count': count})
