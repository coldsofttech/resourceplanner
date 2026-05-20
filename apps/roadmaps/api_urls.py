from rest_framework.routers import DefaultRouter
from .api_views import RoadmapViewSet, RoadmapItemViewSet, RoadmapMilestoneViewSet, RoadmapTaskViewSet

router = DefaultRouter()
router.register(r'roadmaps', RoadmapViewSet, basename='roadmap')
router.register(r'roadmap-items', RoadmapItemViewSet, basename='roadmap-item')
router.register(r'roadmap-milestones', RoadmapMilestoneViewSet, basename='roadmap-milestone')
router.register(r'roadmap-tasks', RoadmapTaskViewSet, basename='roadmap-task')

urlpatterns = router.urls
