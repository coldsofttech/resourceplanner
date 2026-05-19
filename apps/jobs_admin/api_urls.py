from django.urls import path

from .api_views import JobRunView

urlpatterns = [
    path('jobs/<str:job_name>/run/', JobRunView.as_view(), name='job-run'),
]
