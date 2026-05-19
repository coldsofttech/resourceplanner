from django.urls import path

from .views import ProjectApprovalListView

app_name = 'project_approval'

urlpatterns = [
    path('', ProjectApprovalListView.as_view(), name='project_approval'),
]
