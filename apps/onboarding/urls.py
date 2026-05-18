from django.urls import path
from .views import OnboardingFormView

urlpatterns = [
    path('', OnboardingFormView.as_view(), name='onboarding_form'),
]
