from django.urls import path

from .views import (
    EmailTemplateListView,
    EmailTemplateEditorView,
    EmailTemplateHeaderListView,
    EmailTemplateFooterListView,
)

app_name = 'email_templates'

urlpatterns = [
    path('', EmailTemplateListView.as_view(), name='list'),
    path('headers/', EmailTemplateHeaderListView.as_view(), name='headers'),
    path('footers/', EmailTemplateFooterListView.as_view(), name='footers'),
    path('<str:scenario>/editor/', EmailTemplateEditorView.as_view(), name='editor'),
]
