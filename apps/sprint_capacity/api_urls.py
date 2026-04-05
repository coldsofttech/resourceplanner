from rest_framework.routers import DefaultRouter

from .api_views import SprintCapacityViewSet

router = DefaultRouter()
router.register(r'sprint-capacity', SprintCapacityViewSet, basename='sprint-capacity')

urlpatterns = router.urls
