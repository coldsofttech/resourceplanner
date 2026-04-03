from django.urls import path

from .api_views import EmploymentTypeViewSet
from .views import (
    EmploymentTypeListView, EmploymentTypeCreateView,
    EmploymentTypeDetailView, EmploymentTypeUpdateView,
)

app_name = 'employment-types'

urlpatterns = [
    path('', EmploymentTypeListView.as_view(), name='list'),
    path('new/', EmploymentTypeCreateView.as_view(), name='create'),
    path('import/sample/', EmploymentTypeViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    path('<int:pk>/', EmploymentTypeDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', EmploymentTypeUpdateView.as_view(), name='edit'),
]
