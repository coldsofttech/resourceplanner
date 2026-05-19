from django.urls import path
from .views import OnboardingFormView, OnboardingSubmissionsView

urlpatterns = [
    path('', OnboardingFormView.as_view(), name='onboarding_form'),
    path('submissions/', OnboardingSubmissionsView.as_view(), name='onboarding_submissions'),
]
