from django.urls import path

from .api_views import (
    NotificationListView,
    NotificationDetailView,
    NotificationMarkAllReadView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='api-notifications-list'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='api-notifications-mark-all-read'),
    path('notifications/unread-count/', NotificationUnreadCountView.as_view(), name='api-notifications-unread-count'),
    path('notifications/<int:pk>/', NotificationDetailView.as_view(), name='api-notifications-detail'),
]
