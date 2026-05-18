from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import (
    EmailTemplateHeaderViewSet,
    EmailTemplateFooterViewSet,
    EmailTemplateScenariosAPIView,
    EmailTemplateDetailAPIView,
    EmailTemplateVariablesAPIView,
)

router = DefaultRouter()
router.register(r'email-template-headers', EmailTemplateHeaderViewSet, basename='email-template-header')
router.register(r'email-template-footers', EmailTemplateFooterViewSet, basename='email-template-footer')

urlpatterns = router.urls + [
    path('email-templates/', EmailTemplateScenariosAPIView.as_view(), name='api-email-template-scenarios'),
    path('email-templates/<str:scenario>/variables/', EmailTemplateVariablesAPIView.as_view(), name='api-email-template-variables'),
    path('email-templates/<str:scenario>/', EmailTemplateDetailAPIView.as_view(), name='api-email-template-detail'),
]
