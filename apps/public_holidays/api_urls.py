from rest_framework.routers import DefaultRouter

from .api_views import PublicHolidayViewSet

router = DefaultRouter()
router.register(r'holidays', PublicHolidayViewSet, basename='holiday')
urlpatterns = router.urls
