from rest_framework.routers import DefaultRouter

from .api_views import TeamRoleViewSet

router = DefaultRouter()
router.register(r'roles', TeamRoleViewSet, basename='role')
urlpatterns = router.urls
