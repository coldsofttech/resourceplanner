from rest_framework.routers import DefaultRouter

from .api_views import WinViewSet, MonthlyWinViewSet, TeamProductOwnerViewSet

router = DefaultRouter()
router.register(r'wins', WinViewSet, basename='win')
router.register(r'monthly-wins', MonthlyWinViewSet, basename='monthly-win')
router.register(r'team-product-owners', TeamProductOwnerViewSet, basename='team-product-owner')

urlpatterns = router.urls
