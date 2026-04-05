from rest_framework.routers import DefaultRouter

from .api_views import ProjectTypeViewSet

router = DefaultRouter()
router.register(r'project-types', ProjectTypeViewSet, basename='project-type')
urlpatterns = router.urls
