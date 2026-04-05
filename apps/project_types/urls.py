from django.urls import path

from .api_views import ProjectTypeViewSet
from .views import ProjectTypeListView, ProjectTypeCreateView, ProjectTypeDetailView, ProjectTypeUpdateView

app_name = 'project-types'

urlpatterns = [
    path('', ProjectTypeListView.as_view(), name='list'),
    path('new/', ProjectTypeCreateView.as_view(), name='create'),
    path('import/sample/', ProjectTypeViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    path('<int:pk>/', ProjectTypeDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', ProjectTypeUpdateView.as_view(), name='edit'),
]
