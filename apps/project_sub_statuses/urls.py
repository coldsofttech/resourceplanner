from django.urls import path

from .api_views import ProjectSubStatusViewSet
from .views import ProjectSubStatusView

app_name = 'project-sub-statuses'

urlpatterns = [
    path('', ProjectSubStatusView.as_view(), name='project-sub-statuses'),
    path('import/sample/', ProjectSubStatusViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
]
