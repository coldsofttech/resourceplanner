from django.urls import path

from .views import (
    IntegrationAIListView,
    IntegrationEmailListView,
    IntegrationJiraListView,
    IntegrationSSOListView,
)

app_name = 'integrations'

urlpatterns = [
    path('ai/', IntegrationAIListView.as_view(), name='ai'),
    path('email/', IntegrationEmailListView.as_view(), name='email'),
    path('sso/', IntegrationSSOListView.as_view(), name='sso'),
    path('jira/', IntegrationJiraListView.as_view(), name='jira'),
]
