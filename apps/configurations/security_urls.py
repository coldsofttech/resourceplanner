from django.urls import path

from .views import SecurityListView, SecurityPasswordPolicyListView

app_name = 'security'

urlpatterns = [
    path('', SecurityListView.as_view(), name='security'),
    path('password-policy/', SecurityPasswordPolicyListView.as_view(), name='password_policy'),
]
