from rest_framework.routers import DefaultRouter

from .api_views import ProjectViewSet, ProjectViewViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"project-views", ProjectViewViewSet, basename="project-view")
urlpatterns = router.urls
