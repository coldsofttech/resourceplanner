from rest_framework.routers import DefaultRouter

from .api_views import MemberLeaveViewSet

router = DefaultRouter()
router.register(r'leaves', MemberLeaveViewSet, basename='leave')
urlpatterns = router.urls