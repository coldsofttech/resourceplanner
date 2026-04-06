from rest_framework.routers import DefaultRouter

from .api_views import ProgrammeViewSet

router = DefaultRouter()
router.register(r"programmes", ProgrammeViewSet, basename="programme")
urlpatterns = router.urls
