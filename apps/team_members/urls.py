from django.urls import path

from .api_views import TeamMemberViewSet
from .views import TeamMemberListView, TeamMemberCreateView, TeamMemberDetailView, TeamMemberUpdateView

app_name = 'team-members'

urlpatterns = [
    path('', TeamMemberListView.as_view(), name='list'),  # list all team members
    path('new/', TeamMemberCreateView.as_view(), name='create'),  # create a new team member
    path('import/sample/', TeamMemberViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    # download sample import template
    path('<int:pk>/', TeamMemberDetailView.as_view(), name='detail'),  # view the specified team member
    path('<int:pk>/edit/', TeamMemberUpdateView.as_view(), name='edit'),  # update the specified team member
]
