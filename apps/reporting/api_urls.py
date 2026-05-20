from django.urls import path

from .api_views import (
    CustomReportDataSourcesView,
    CustomReportDetailView,
    CustomReportExecuteView,
    CustomReportExportView,
    CustomReportListCreateView,
    CustomReportPreviewView,
    CustomReportShareView,
    KPIReportConfigureView,
    KPIReportDataView,
    KPIReportExportView,
    KPIReportMonthListView,
    MonthlyFinanceDataView,
    MonthlyFinanceExportView,
    MonthlyFinanceMonthListView,
    ReportDetailView,
    ReportListCreateView,
    SprintFAFinancialYearListView,
    SprintFAReportDataView,
    SprintFAReportExportView,
    SprintFASprintListView,
    StandardReportConfigureView,
    StandardReportDataView,
    StandardReportExportView,
    StandardReportMappingDetailView,
    StandardReportMappingListCreateView,
    StandardReportMetaView,
)

_FA_SLUG      = 'sprint-forecast-actuals'
_KPI_SLUG     = 'kpi-estimate-accuracy'
_FINANCE_SLUG = 'monthly-finance'

urlpatterns = [
    # Report registry
    path("reports/", ReportListCreateView.as_view(), name="report-list-create"),
    path("reports/<int:pk>/", ReportDetailView.as_view(), name="report-detail"),

    # Sprint Forecast vs. Actuals — specific routes BEFORE generic slug routes
    path(
        f"reports/standard/{_FA_SLUG}/data/",
        SprintFAReportDataView.as_view(),
        name="sprint-fa-report-data",
    ),
    path(
        f"reports/standard/{_FA_SLUG}/export/",
        SprintFAReportExportView.as_view(),
        name="sprint-fa-report-export",
    ),
    path(
        f"reports/standard/{_FA_SLUG}/sprints/",
        SprintFASprintListView.as_view(),
        name="sprint-fa-sprint-list",
    ),
    path(
        f"reports/standard/{_FA_SLUG}/financial-years/",
        SprintFAFinancialYearListView.as_view(),
        name="sprint-fa-fy-list",
    ),

    # Monthly Finance Report — specific routes BEFORE generic slug routes
    path(
        f"reports/standard/{_FINANCE_SLUG}/months/",
        MonthlyFinanceMonthListView.as_view(),
        name="monthly-finance-months",
    ),
    path(
        f"reports/standard/{_FINANCE_SLUG}/data/",
        MonthlyFinanceDataView.as_view(),
        name="monthly-finance-data",
    ),
    path(
        f"reports/standard/{_FINANCE_SLUG}/export/",
        MonthlyFinanceExportView.as_view(),
        name="monthly-finance-export",
    ),

    # KPI Estimate % Accuracy — specific routes BEFORE generic slug routes
    path(
        f"reports/standard/{_KPI_SLUG}/months/",
        KPIReportMonthListView.as_view(),
        name="kpi-report-months",
    ),
    path(
        f"reports/standard/{_KPI_SLUG}/data/",
        KPIReportDataView.as_view(),
        name="kpi-report-data",
    ),
    path(
        f"reports/standard/{_KPI_SLUG}/export/",
        KPIReportExportView.as_view(),
        name="kpi-report-export",
    ),
    path(
        f"reports/standard/{_KPI_SLUG}/configure/",
        KPIReportConfigureView.as_view(),
        name="kpi-report-configure",
    ),

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

    # Custom Reports
    path("custom-reports/data-sources/",
         CustomReportDataSourcesView.as_view(), name="custom-report-data-sources"),
    path("custom-reports/preview/",
         CustomReportPreviewView.as_view(), name="custom-report-preview"),
    path("custom-reports/",
         CustomReportListCreateView.as_view(), name="custom-report-list-create"),
    path("custom-reports/<int:pk>/",
         CustomReportDetailView.as_view(), name="custom-report-detail"),
    path("custom-reports/<int:pk>/execute/",
         CustomReportExecuteView.as_view(), name="custom-report-execute"),
    path("custom-reports/<int:pk>/export/",
         CustomReportExportView.as_view(), name="custom-report-export"),
    path("custom-reports/<int:pk>/share/",
         CustomReportShareView.as_view(), name="custom-report-share"),
    path("custom-reports/<int:pk>/share/<int:user_id>/",
         CustomReportShareView.as_view(), name="custom-report-share-delete"),
]
