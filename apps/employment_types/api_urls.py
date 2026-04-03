from rest_framework.routers import DefaultRouter

from .api_views import EmploymentTypeViewSet

router = DefaultRouter()
router.register(r'employment-types', EmploymentTypeViewSet, basename='employment-type')
urlpatterns = router.urls
