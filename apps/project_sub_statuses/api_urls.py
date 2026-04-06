from rest_framework.routers import DefaultRouter

from .api_views import ProjectSubStatusViewSet

router = DefaultRouter()
router.register(r'project-sub-statuses', ProjectSubStatusViewSet, basename='project-sub-status')
urlpatterns = router.urls
