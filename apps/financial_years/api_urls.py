from rest_framework.routers import DefaultRouter

from .api_views import FinancialYearViewSet

router = DefaultRouter()
router.register(r'fy', FinancialYearViewSet, basename='fy')
urlpatterns = router.urls
