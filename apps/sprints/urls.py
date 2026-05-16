from django.urls import path

from .views import SprintListView, SprintCreateView, SprintDetailView, SprintUpdateView
from apps.sprint_forecast.views import SprintForecastPageView, ForecastImportDetailPageView

app_name = 'sprints'

urlpatterns = [
    path('', SprintListView.as_view(), name='list'),
    path('new/', SprintCreateView.as_view(), name='create'),
    path('<int:pk>/', SprintDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', SprintUpdateView.as_view(), name='edit'),
    path('<int:pk>/forecast/', SprintForecastPageView.as_view(), name='forecast'),
    path('<int:pk>/forecast/<int:import_pk>/', ForecastImportDetailPageView.as_view(), name='forecast-import-detail'),
]
