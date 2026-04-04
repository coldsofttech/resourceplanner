from django.urls import path

from .api_views import DeliveryTeamViewSet
from .views import DeliveryTeamListView, DeliveryTeamCreateView, DeliveryTeamDetailView, DeliveryTeamUpdateView

app_name = 'delivery-teams'

urlpatterns = [
    path('', DeliveryTeamListView.as_view(), name='list'),  # list all delivery teams
    path('new/', DeliveryTeamCreateView.as_view(), name='create'),  # create a new delivery team
    path('import/sample/', DeliveryTeamViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    # download sample import template
    path('<int:pk>/', DeliveryTeamDetailView.as_view(), name='detail'),  # view the specified delivery team
    path('<int:pk>/edit/', DeliveryTeamUpdateView.as_view(), name='edit'),  # update the specified delivery team
]
