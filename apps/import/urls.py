from django.urls import path

from .views import ImportView

app_name = 'import'

urlpatterns = [
    path('', ImportView.as_view(), name='import')
]
