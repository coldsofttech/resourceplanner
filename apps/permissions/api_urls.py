from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import PermissionListView, PermissionCategoryViewSet

router = DefaultRouter()
router.register(r'permission-categories', PermissionCategoryViewSet, basename='permission-category')

urlpatterns = [
    path('permissions/', PermissionListView.as_view(), name='permission-list'),
] + router.urls
