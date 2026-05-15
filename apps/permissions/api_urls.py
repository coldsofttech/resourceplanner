from django.urls import path
from .api_views import PermissionListView

urlpatterns = [
    path('permissions/', PermissionListView.as_view(), name='permission-list'),
]
