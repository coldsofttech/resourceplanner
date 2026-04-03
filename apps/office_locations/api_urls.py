from rest_framework.routers import DefaultRouter

from .api_views import OfficeLocationViewSet

router = DefaultRouter()
router.register(r'locations', OfficeLocationViewSet, basename='location')
urlpatterns = router.urls
