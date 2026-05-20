from django.urls import path

from .views import (
    CustomReportEditorView,
    CustomReportListView,
    ReportingIndexView,
    StandardReportConfigureView,
    StandardReportView,
)

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
    path("custom/", CustomReportListView.as_view(), name="custom-report-list"),
    path("custom/new/", CustomReportEditorView.as_view(), name="custom-report-new"),
    path("custom/<int:pk>/", CustomReportEditorView.as_view(), name="custom-report-editor"),
]
