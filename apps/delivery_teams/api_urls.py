from rest_framework.routers import DefaultRouter

from .api_views import DeliveryTeamViewSet

router = DefaultRouter()
router.register(r'delivery-teams', DeliveryTeamViewSet, basename='delivery-team')
urlpatterns = router.urls
