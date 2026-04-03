from django.urls import path

from .views import ConfigurationListView, ConfigurationDetailView, ConfigurationUpdateView

app_name = 'configurations'

urlpatterns = [
    path('', ConfigurationListView.as_view(), name='list'),  # list all configurations
    path('<int:pk>/', ConfigurationDetailView.as_view(), name='detail'),  # view the specified configuration
    path('<int:pk>/edit/', ConfigurationUpdateView.as_view(), name='edit'),  # update the specified configuration
]
