from django.urls import path

from .api_views import (
    ReportDetailView,
    ReportListCreateView,
    StandardReportConfigureView,
    StandardReportDataView,
    StandardReportExportView,
    StandardReportMappingDetailView,
    StandardReportMappingListCreateView,
    StandardReportMetaView,
)

urlpatterns = [
    # Report registry
    path("reports/", ReportListCreateView.as_view(), name="report-list-create"),
    path("reports/<int:pk>/", ReportDetailView.as_view(), name="report-detail"),

    # Standard report endpoints (slug-based)
    path(
        "reports/standard/<slug:slug>/",
        StandardReportMetaView.as_view(),
        name="standard-report-meta",
    ),
    path(
        "reports/standard/<slug:slug>/data/",
        StandardReportDataView.as_view(),
        name="standard-report-data",
    ),
    path(
        "reports/standard/<slug:slug>/export/",
        StandardReportExportView.as_view(),
        name="standard-report-export",
    ),
    path(
        "reports/standard/<slug:slug>/configure/",
        StandardReportConfigureView.as_view(),
        name="standard-report-configure",
    ),
    path(
        "reports/standard/<slug:slug>/configure/mapping/",
        StandardReportMappingListCreateView.as_view(),
        name="standard-report-mapping-list",
    ),
    path(
        "reports/standard/<slug:slug>/configure/mapping/<int:pk>/",
        StandardReportMappingDetailView.as_view(),
        name="standard-report-mapping-detail",
    ),
]
