from rest_framework.routers import DefaultRouter
from .api_views import UserViewSet, UserGroupViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'user-groups', UserGroupViewSet, basename='user-group')

urlpatterns = router.urls
