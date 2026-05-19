from django.urls import path

from .module_api_views import (
    IntegrationAIAPIView,
    IntegrationEmailAPIView,
    IntegrationSSOAPIView,
    IntegrationJiraAPIView,
    SecurityAPIView,
    SecurityPasswordPolicyAPIView,
    ProjectApprovalAPIView,
    RechargeContactsAPIView,
)

urlpatterns = [
    path('integrations/ai/', IntegrationAIAPIView.as_view(), name='api-integration-ai'),
    path('integrations/email/', IntegrationEmailAPIView.as_view(), name='api-integration-email'),
    path('integrations/sso/', IntegrationSSOAPIView.as_view(), name='api-integration-sso'),
    path('integrations/jira/', IntegrationJiraAPIView.as_view(), name='api-integration-jira'),
    path('security/', SecurityAPIView.as_view(), name='api-security'),
    path('security/password-policy/', SecurityPasswordPolicyAPIView.as_view(), name='api-security-password-policy'),
    path('project-approval/', ProjectApprovalAPIView.as_view(), name='api-project-approval'),
    path('recharge-contacts/', RechargeContactsAPIView.as_view(), name='api-recharge-contacts'),
]
