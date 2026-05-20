from rest_framework.routers import DefaultRouter
from .api_views import RoadmapViewSet, RoadmapItemViewSet, RoadmapMilestoneViewSet

router = DefaultRouter()
router.register(r'roadmaps', RoadmapViewSet, basename='roadmap')
router.register(r'roadmap-items', RoadmapItemViewSet, basename='roadmap-item')
router.register(r'roadmap-milestones', RoadmapMilestoneViewSet, basename='roadmap-milestone')

urlpatterns = router.urls
