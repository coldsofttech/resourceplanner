from django.urls import path

from .api_views import OfficeLocationViewSet
from .views import OfficeLocationListView, OfficeLocationCreateView, OfficeLocationDetailView, OfficeLocationUpdateView

app_name = 'locations'

urlpatterns = [
    path('', OfficeLocationListView.as_view(), name='list'),  # list all office locations
    path('new/', OfficeLocationCreateView.as_view(), name='create'),  # create a new office location
    path('import/sample/', OfficeLocationViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    # download sample import template
    path('<int:pk>/', OfficeLocationDetailView.as_view(), name='detail'),  # view the specified office location
    path('<int:pk>/edit/', OfficeLocationUpdateView.as_view(), name='edit'),  # update the specified office location
]
