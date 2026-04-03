from django.urls import path

from .api_views import TeamRoleViewSet
from .views import TeamRoleListView, TeamRoleCreateView, TeamRoleDetailView, TeamRoleUpdateView

app_name = 'roles'

urlpatterns = [
    path('', TeamRoleListView.as_view(), name='list'),  # list all roles
    path('new/', TeamRoleCreateView.as_view(), name='create'),  # create a new role
    path('import/sample/', TeamRoleViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    # download sample import template
    path('<int:pk>/', TeamRoleDetailView.as_view(), name='detail'),  # view the specified role
    path('<int:pk>/edit/', TeamRoleUpdateView.as_view(), name='edit'),  # update the specified role
]
