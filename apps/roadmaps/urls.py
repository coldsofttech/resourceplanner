from django.urls import path
from .views import RoadmapListView, RoadmapDetailView

app_name = 'roadmaps'

urlpatterns = [
    path('', RoadmapListView.as_view(), name='list'),
    path('<int:pk>/', RoadmapDetailView.as_view(), name='detail'),
]
