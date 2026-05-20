from django.urls import path

from . import views

urlpatterns = [
    path('', views.org_chart, name='org-chart'),
]
