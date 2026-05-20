from django.urls import path

from . import views

urlpatterns = [
    path('',      views.SetupWizardView.as_view(), name='setup-wizard'),
    path('step/', views.SetupStepView.as_view(),   name='setup-step'),
]
