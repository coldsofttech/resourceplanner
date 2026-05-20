from django.urls import path

from .views import DatabaseConfigView

urlpatterns = [
    path('', DatabaseConfigView.as_view(), name='database-config'),
]
