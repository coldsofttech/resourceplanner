from django.urls import path

from .views import ReportingIndexView, StandardReportConfigureView, StandardReportView

app_name = "reporting"

urlpatterns = [
    path("", ReportingIndexView.as_view(), name="index"),
    path(
        "standard/<slug:slug>/",
        StandardReportView.as_view(),
        name="standard-report",
    ),
    path(
        "standard/<slug:slug>/configure/",
        StandardReportConfigureView.as_view(),
        name="standard-report-configure",
    ),
]
