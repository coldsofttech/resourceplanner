from django.urls import path
from .login_view import LoginView, RefreshView

urlpatterns = [
    path('login/', LoginView.as_view(), name='api-login'),
    path('refresh/', RefreshView.as_view(), name='api-token-refresh'),
]
