import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils import view_set_validation_details

from .models import DemandCapacityConfig, ProgrammeCategoryMapping, Report
from .serializers import (
    BulkMappingUpsertSerializer,
    CustomReportCreateSerializer,
    DemandCapacityConfigSerializer,
    KPIBulkCommentSerializer,
    MappingUpsertSerializer,
    ProgrammeCategoryMappingSerializer,
    ReportSerializer,
)
from .services import (
    REPORT_REGISTRY,
    DemandCapacityConfigService,
    DemandCapacityService,
    KPIReportService,
    MonthlyFinanceReportService,
    ReportService,
    SprintForecastActualsService,
)

logger = logging.getLogger(__name__)


def _db_error_response(e, action=""):
    logger.exception("DatabaseError in %s: %s", action, e)
    return Response(
        {"error": "A database error occurred. Please try again later."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _unexpected_error_response(e, action=""):
    logger.exception("Unexpected error in %s: %s", action, e)
    return Response(
        {"error": "An unexpected error occurred. Please try again later."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _parse_int_param(params, key, default=None):
    val = params.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# GET /api/v1/reports/
# POST /api/v1/reports/
# ---------------------------------------------------------------------------

class ReportListCreateView(APIView):
    def get(self, request):
        try:
            report_type = request.query_params.get("type")
            reports = ReportService.list_reports(report_type=report_type)
            return Response(
                {"results": ReportSerializer(reports, many=True).data},
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            return _db_error_response(e, "report list")
        except Exception as e:
            return _unexpected_error_response(e, "report list")

    def post(self, request):
        try:
            serializer = CustomReportCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            report = ReportService.create_custom_report(
                serializer.validated_data, user=request.user
            )
            return Response(
                ReportSerializer(report).data, status=status.HTTP_201_CREATED
            )
        except (DjangoValidationError, DRFValidationError) as e:
            return Response(
                {"error": "Invalid data.", "details": view_set_validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            return _db_error_response(e, "report create")
        except Exception as e:
            return _unexpected_error_response(e, "report create")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/<id>/   (custom report detail)
# ---------------------------------------------------------------------------

class ReportDetailView(APIView):
    def get(self, request, pk):
        try:
            report = Report.objects.get(pk=pk)
            return Response(ReportSerializer(report).data)
        except Report.DoesNotExist:
            return Response({"error": "Report not found."}, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            return _db_error_response(e, "report detail")
        except Exception as e:
            return _unexpected_error_response(e, "report detail")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/<slug>/
# ---------------------------------------------------------------------------

class StandardReportMetaView(APIView):
    def get(self, request, slug):
        try:
            report = ReportService.get_report_by_slug(slug)
            return Response(ReportSerializer(report).data)
        except Report.DoesNotExist:
            return Response(
                {"error": "Report not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except DatabaseError as e:
            return _db_error_response(e, "standard report meta")
        except Exception as e:
            return _unexpected_error_response(e, "standard report meta")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/<slug>/data/
# ---------------------------------------------------------------------------

class StandardReportDataView(APIView):
    def get(self, request, slug):
        try:
            plan_id = _parse_int_param(request.query_params, "plan")
            version_id = _parse_int_param(request.query_params, "version")
            team_id = _parse_int_param(request.query_params, "team")
            employee_type_id = _parse_int_param(
                request.query_params, "employee_type"
            )

            if not plan_id or not version_id:
                return Response(
                    {"error": "'plan' and 'version' query parameters are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            service_cls = REPORT_REGISTRY.get(slug)
            if service_cls is None:
                return Response(
                    {"error": f"No data service registered for report '{slug}'."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            data = service_cls.get_data(
                plan_id=plan_id,
                version_id=version_id,
                team_id=team_id,
                employee_type_id=employee_type_id,
            )
            if data is None:
                return Response(
                    {"error": "Plan or version not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response = Response(data, status=status.HTTP_200_OK)
            response["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response["Pragma"] = "no-cache"
            return response

        except DatabaseError as e:
            return _db_error_response(e, "report data")
        except Exception as e:
            return _unexpected_error_response(e, "report data")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/<slug>/export/
# ---------------------------------------------------------------------------

class StandardReportExportView(APIView):
    def get(self, request, slug):
        try:
            plan_id = _parse_int_param(request.query_params, "plan")
            version_id = _parse_int_param(request.query_params, "version")
            team_id = _parse_int_param(request.query_params, "team")
            employee_type_id = _parse_int_param(
                request.query_params, "employee_type"
            )
            fmt = request.query_params.get("fmt", "csv").lower()

            if not plan_id or not version_id:
                return Response(
                    {"error": "'plan' and 'version' query parameters are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            service_cls = REPORT_REGISTRY.get(slug)
            if service_cls is None:
                return Response(
                    {"error": f"No service registered for '{slug}'."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            data = service_cls.get_data(
                plan_id=plan_id,
                version_id=version_id,
                team_id=team_id,
                employee_type_id=employee_type_id,
            )
            if data is None:
                return Response(
                    {"error": "Plan or version not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            plan_name = data["plan"]["name"].replace(" ", "_")
            version_num = data["version"]["version"]
            base_filename = f"{slug}_{plan_name}_v{version_num}"

            if fmt == "xlsx":
                content = service_cls.export_xlsx(data)
                response = HttpResponse(
                    content,
                    content_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    ),
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="{base_filename}.xlsx"'
                )
                return response

            # Default: CSV
            content = service_cls.export_csv(data)
            response = HttpResponse(
                content, content_type="text/csv; charset=utf-8-sig"
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{base_filename}.csv"'
            )
            return response

        except DatabaseError as e:
            return _db_error_response(e, "report export")
        except Exception as e:
            return _unexpected_error_response(e, "report export")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/sprint-forecast-actuals/data/
# ---------------------------------------------------------------------------

class SprintFAReportDataView(APIView):
    def get(self, request):
        try:
            sprint_id = _parse_int_param(request.query_params, 'sprint')
            team_id = _parse_int_param(request.query_params, 'team')

            if not sprint_id:
                return Response(
                    {'error': "'sprint' query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = SprintForecastActualsService.get_data(sprint_id=sprint_id, team_id=team_id)
            if data is None:
                return Response({'error': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)

            response = Response(data, status=status.HTTP_200_OK)
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response['Pragma'] = 'no-cache'
            return response

        except DatabaseError as e:
            return _db_error_response(e, 'sprint fa data')
        except Exception as e:
            return _unexpected_error_response(e, 'sprint fa data')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/sprint-forecast-actuals/export/
# ---------------------------------------------------------------------------

class SprintFAReportExportView(APIView):
    def get(self, request):
        try:
            sprint_id = _parse_int_param(request.query_params, 'sprint')
            team_id = _parse_int_param(request.query_params, 'team')
            fmt = request.query_params.get('fmt', 'csv').lower()

            if not sprint_id:
                return Response(
                    {'error': "'sprint' query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = SprintForecastActualsService.get_data(sprint_id=sprint_id, team_id=team_id)
            if data is None:
                return Response({'error': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)

            sprint_name = data['sprint']['name'].replace(' ', '_')
            base_filename = f"sprint_fa_{sprint_name}"

            if fmt == 'xlsx':
                content = SprintForecastActualsService.export_xlsx(data, sprint_name)
                resp = HttpResponse(
                    content,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
                resp['Content-Disposition'] = f'attachment; filename="{base_filename}.xlsx"'
                return resp

            content = SprintForecastActualsService.export_csv(data, sprint_name)
            resp = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
            resp['Content-Disposition'] = f'attachment; filename="{base_filename}.csv"'
            return resp

        except DatabaseError as e:
            return _db_error_response(e, 'sprint fa export')
        except Exception as e:
            return _unexpected_error_response(e, 'sprint fa export')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/sprint-forecast-actuals/sprints/
# ---------------------------------------------------------------------------

class SprintFASprintListView(APIView):
    def get(self, request):
        try:
            from apps.sprints.models import Sprint
            qs = Sprint.objects.select_related('financial_year').order_by('-start_date')
            fy_id = _parse_int_param(request.query_params, 'fy')
            if fy_id:
                qs = qs.filter(financial_year_id=fy_id)
            sprints = [
                {'id': s.id, 'sprint_name': s.sprint_name}
                for s in qs[:200]
            ]
            return Response({'results': sprints}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            return _db_error_response(e, 'sprint fa sprint list')
        except Exception as e:
            return _unexpected_error_response(e, 'sprint fa sprint list')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/sprint-forecast-actuals/financial-years/
# ---------------------------------------------------------------------------

class SprintFAFinancialYearListView(APIView):
    def get(self, request):
        try:
            from apps.financial_years.models import FinancialYear
            fys = list(
                FinancialYear.objects.order_by('-start_date').values('id', 'long_fy', 'short_fy')
            )
            return Response({'results': fys}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            return _db_error_response(e, 'sprint fa fy list')
        except Exception as e:
            return _unexpected_error_response(e, 'sprint fa fy list')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/<slug>/configure/
# POST /api/v1/reports/standard/<slug>/configure/
# ---------------------------------------------------------------------------

class StandardReportConfigureView(APIView):
    def _get_plan_version(self, request):
        plan_id = _parse_int_param(request.query_params, "plan")
        version_id = _parse_int_param(request.query_params, "version")
        if not plan_id or not version_id:
            return None, None, Response(
                {"error": "'plan' and 'version' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return plan_id, version_id, None

    def get(self, request, slug):
        try:
            plan_id, version_id, err = self._get_plan_version(request)
            if err:
                return err

            result = DemandCapacityConfigService.get_configure_data(plan_id, version_id)
            if result is None:
                return Response(
                    {"error": "Plan or version not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            config_data = (
                DemandCapacityConfigSerializer(result["config"]).data
                if result["config"]
                else None
            )
            mappings = (
                [
                    {
                        "id": m.id,
                        "programme_id": m.programme_id,
                        "programme_name": m.programme.name,
                        "category_label": m.category_label,
                    }
                    for m in result["mapping_dict"].values()
                ]
                if result["mapping_dict"]
                else []
            )
            programmes = [
                {"id": p.id, "name": p.name}
                for p in result["programmes"]
            ]

            return Response(
                {
                    "plan": {"id": result["plan"].id, "name": result["plan"].name},
                    "version": {
                        "id": result["version"].id,
                        "version": result["version"].version,
                        "status": result["version"].status,
                    },
                    "config": config_data,
                    "programmes": programmes,
                    "mappings": mappings,
                },
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            return _db_error_response(e, "configure get")
        except Exception as e:
            return _unexpected_error_response(e, "configure get")

    def post(self, request, slug):
        """Bulk upsert mappings."""
        try:
            plan_id, version_id, err = self._get_plan_version(request)
            if err:
                return err

            serializer = BulkMappingUpsertSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            results = DemandCapacityConfigService.bulk_upsert_mappings(
                plan_id=plan_id,
                version_id=version_id,
                mappings=serializer.validated_data["mappings"],
                user=request.user,
            )
            mapping_objs = [r["mapping"] for r in results]
            return Response(
                ProgrammeCategoryMappingSerializer(mapping_objs, many=True).data,
                status=status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError) as e:
            return Response(
                {"error": "Invalid data.", "details": view_set_validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            return _db_error_response(e, "configure post")
        except Exception as e:
            return _unexpected_error_response(e, "configure post")


# ---------------------------------------------------------------------------
# GET  /api/v1/reports/standard/<slug>/configure/mapping/
# POST /api/v1/reports/standard/<slug>/configure/mapping/
# ---------------------------------------------------------------------------

class StandardReportMappingListCreateView(APIView):
    def _get_plan_version(self, request):
        plan_id = _parse_int_param(request.query_params, "plan")
        version_id = _parse_int_param(request.query_params, "version")
        if not plan_id or not version_id:
            return None, None, Response(
                {"error": "'plan' and 'version' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return plan_id, version_id, None

    def get(self, request, slug):
        try:
            plan_id, version_id, err = self._get_plan_version(request)
            if err:
                return err

            mappings = DemandCapacityConfigService.list_mappings(plan_id, version_id)
            return Response(
                ProgrammeCategoryMappingSerializer(mappings, many=True).data,
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            return _db_error_response(e, "mapping list")
        except Exception as e:
            return _unexpected_error_response(e, "mapping list")

    def post(self, request, slug):
        try:
            plan_id, version_id, err = self._get_plan_version(request)
            if err:
                return err

            serializer = MappingUpsertSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            mapping, created = DemandCapacityConfigService.upsert_mapping(
                plan_id=plan_id,
                version_id=version_id,
                programme_id=serializer.validated_data["programme_id"],
                category_label=serializer.validated_data["category_label"],
                user=request.user,
            )
            return Response(
                ProgrammeCategoryMappingSerializer(mapping).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError) as e:
            return Response(
                {"error": "Invalid data.", "details": view_set_validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            return _db_error_response(e, "mapping create")
        except Exception as e:
            return _unexpected_error_response(e, "mapping create")


# ---------------------------------------------------------------------------
# DELETE /api/v1/reports/standard/<slug>/configure/mapping/<pk>/
# ---------------------------------------------------------------------------

class StandardReportMappingDetailView(APIView):
    def delete(self, request, slug, pk):
        try:
            DemandCapacityConfigService.delete_mapping(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except DatabaseError as e:
            return _db_error_response(e, "mapping delete")
        except Exception as e:
            return _unexpected_error_response(e, "mapping delete")


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/kpi-estimate-accuracy/months/
# ---------------------------------------------------------------------------

class KPIReportMonthListView(APIView):
    def get(self, request):
        try:
            months = KPIReportService.get_months()
            return Response({'results': months}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            return _db_error_response(e, 'kpi months list')
        except Exception as e:
            return _unexpected_error_response(e, 'kpi months list')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/kpi-estimate-accuracy/data/?month=YYYY-MM
# ---------------------------------------------------------------------------

class KPIReportDataView(APIView):
    def get(self, request):
        try:
            month_str = request.query_params.get('month', '').strip()
            if not month_str:
                return Response(
                    {'error': "'month' query parameter is required (format: YYYY-MM)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = KPIReportService.get_data(month_str)
            if data is None:
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            response = Response(data, status=status.HTTP_200_OK)
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response['Pragma'] = 'no-cache'
            return response
        except DatabaseError as e:
            return _db_error_response(e, 'kpi data')
        except Exception as e:
            return _unexpected_error_response(e, 'kpi data')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/kpi-estimate-accuracy/export/?month=YYYY-MM&fmt=csv|xlsx|pdf
# ---------------------------------------------------------------------------

class KPIReportExportView(APIView):
    def get(self, request):
        try:
            month_str = request.query_params.get('month', '').strip()
            fmt       = request.query_params.get('fmt', 'csv').lower()

            if not month_str:
                return Response(
                    {'error': "'month' query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = KPIReportService.get_data(month_str)
            if data is None:
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            safe_month = month_str.replace('-', '_')
            base_name  = f"kpi_estimate_accuracy_{safe_month}"

            if fmt == 'xlsx':
                content  = KPIReportService.export_xlsx(data)
                response = HttpResponse(
                    content,
                    content_type=(
                        'application/vnd.openxmlformats-officedocument'
                        '.spreadsheetml.sheet'
                    ),
                )
                response['Content-Disposition'] = (
                    f'attachment; filename="{base_name}.xlsx"'
                )
                return response

            if fmt == 'pdf':
                content  = KPIReportService.export_pdf(data)
                response = HttpResponse(content, content_type='application/pdf')
                response['Content-Disposition'] = (
                    f'attachment; filename="{base_name}.pdf"'
                )
                return response

            # Default: CSV
            content  = KPIReportService.export_csv(data)
            response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = (
                f'attachment; filename="{base_name}.csv"'
            )
            return response

        except DatabaseError as e:
            return _db_error_response(e, 'kpi export')
        except Exception as e:
            return _unexpected_error_response(e, 'kpi export')


# ---------------------------------------------------------------------------
# GET  /api/v1/reports/standard/kpi-estimate-accuracy/configure/?month=YYYY-MM
# POST /api/v1/reports/standard/kpi-estimate-accuracy/configure/?month=YYYY-MM
# ---------------------------------------------------------------------------

class KPIReportConfigureView(APIView):
    def _get_month(self, request):
        month_str = request.query_params.get('month', '').strip()
        if not month_str:
            return None, Response(
                {'error': "'month' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return month_str, None

    def get(self, request):
        try:
            month_str, err = self._get_month(request)
            if err:
                return err

            result = KPIReportService.get_configure_data(month_str)
            if result is None:
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            return _db_error_response(e, 'kpi configure get')
        except Exception as e:
            return _unexpected_error_response(e, 'kpi configure get')

    def post(self, request):
        try:
            month_str, err = self._get_month(request)
            if err:
                return err

            serializer = KPIBulkCommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            KPIReportService.save_comments(
                month_str=month_str,
                comments=serializer.validated_data['comments'],
                user=request.user,
            )

            result = KPIReportService.get_configure_data(month_str)
            return Response(result, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError) as e:
            return Response(
                {'error': 'Invalid data.', 'details': view_set_validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            return _db_error_response(e, 'kpi configure post')
        except Exception as e:
            return _unexpected_error_response(e, 'kpi configure post')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/monthly-finance/months/
# ---------------------------------------------------------------------------

class MonthlyFinanceMonthListView(APIView):
    def get(self, request):
        try:
            months = MonthlyFinanceReportService.get_months()
            return Response({'results': months}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            return _db_error_response(e, 'monthly finance months')
        except Exception as e:
            return _unexpected_error_response(e, 'monthly finance months')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/monthly-finance/data/?month=YYYY-MM
# ---------------------------------------------------------------------------

class MonthlyFinanceDataView(APIView):
    def get(self, request):
        try:
            month_str = request.query_params.get('month', '').strip()
            if not month_str:
                return Response(
                    {'error': "'month' query parameter is required (format: YYYY-MM)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data = MonthlyFinanceReportService.get_data(month_str)
            if data is None:
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            response = Response(data, status=status.HTTP_200_OK)
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response['Pragma'] = 'no-cache'
            return response
        except DatabaseError as e:
            return _db_error_response(e, 'monthly finance data')
        except Exception as e:
            return _unexpected_error_response(e, 'monthly finance data')


# ---------------------------------------------------------------------------
# GET /api/v1/reports/standard/monthly-finance/export/?month=YYYY-MM&fmt=csv|xlsx
# ---------------------------------------------------------------------------

class MonthlyFinanceExportView(APIView):
    def get(self, request):
        try:
            month_str = request.query_params.get('month', '').strip()
            fmt       = request.query_params.get('fmt', 'csv').lower()

            if not month_str:
                return Response(
                    {'error': "'month' query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = MonthlyFinanceReportService.get_data(month_str)
            if data is None:
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if data.get('error'):
                return Response(
                    {'error': 'Report cannot be exported — not all sprints have actuals confirmed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            safe_month = month_str.replace('-', '_')
            base_name  = f"monthly_finance_{safe_month}"

            if fmt == 'xlsx':
                content  = MonthlyFinanceReportService.export_xlsx(data)
                response = HttpResponse(
                    content,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
                response['Content-Disposition'] = f'attachment; filename="{base_name}.xlsx"'
                return response

            content  = MonthlyFinanceReportService.export_csv(data)
            response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="{base_name}.csv"'
            return response

        except DatabaseError as e:
            return _db_error_response(e, 'monthly finance export')
        except Exception as e:
            return _unexpected_error_response(e, 'monthly finance export')


# ─────────────────────────────────────────────────────────────────────────────
# Custom Reports
# ─────────────────────────────────────────────────────────────────────────────

class CustomReportDataSourcesView(APIView):
    """GET /api/v1/custom-reports/data-sources/"""

    def get(self, request):
        from .data_sources import list_data_sources
        sources = list_data_sources()
        # Filter to sources the user has access to
        if not request.user.is_staff:
            sources = [
                s for s in sources
                if request.user.has_module_perms(s['app_label'])
                or s['app_label'] in ('wins', 'financial_years')  # open to all authenticated
            ]
        return Response(sources)


class CustomReportListCreateView(APIView):
    """
    GET  /api/v1/custom-reports/   — list user's own + shared reports
    POST /api/v1/custom-reports/   — create a new report
    """

    def get(self, request):
        from django.db.models import Q as DQ
        from .models import CustomReport
        from .serializers import CustomReportSerializer
        qs = (
            CustomReport.objects
            .filter(DQ(owner=request.user) | DQ(shares__user=request.user))
            .distinct()
            .prefetch_related('shares__user')
            .select_related('owner')
        )
        return Response(CustomReportSerializer(qs, many=True, context={'request': request}).data)

    def post(self, request):
        from .models import CustomReport
        from .serializers import CustomReportWriteSerializer, CustomReportSerializer
        ser = CustomReportWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        report = ser.save(owner=request.user, created_by=request.user, updated_by=request.user)
        return Response(
            CustomReportSerializer(report, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class CustomReportDetailView(APIView):
    """
    GET    /api/v1/custom-reports/{pk}/
    PATCH  /api/v1/custom-reports/{pk}/
    DELETE /api/v1/custom-reports/{pk}/
    """

    def _get_report(self, pk, user, require_edit=False):
        from .models import CustomReport
        try:
            report = (
                CustomReport.objects
                .prefetch_related('shares__user')
                .select_related('owner')
                .get(pk=pk)
            )
        except CustomReport.DoesNotExist:
            return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if require_edit and not report.can_edit(user):
            return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        if not require_edit and not report.can_view(user):
            return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        return report, None

    def get(self, request, pk):
        report, err = self._get_report(pk, request.user)
        if err:
            return err
        from .serializers import CustomReportSerializer
        return Response(CustomReportSerializer(report, context={'request': request}).data)

    def patch(self, request, pk):
        report, err = self._get_report(pk, request.user, require_edit=True)
        if err:
            return err
        from .serializers import CustomReportWriteSerializer, CustomReportSerializer
        ser = CustomReportWriteSerializer(report, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        ser.save(updated_by=request.user)
        return Response(CustomReportSerializer(report, context={'request': request}).data)

    def delete(self, request, pk):
        from .models import CustomReport
        try:
            report = CustomReport.objects.get(pk=pk)
        except CustomReport.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if report.owner_id != request.user.pk and not request.user.is_staff:
            return Response({'detail': 'Only the owner can delete this report.'}, status=status.HTTP_403_FORBIDDEN)
        report.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomReportPreviewView(APIView):
    """POST /api/v1/custom-reports/preview/ — execute without a saved report."""

    def post(self, request):
        from .data_sources import get_data_source
        from .query_engine import execute

        data_source   = request.data.get('data_source', '')
        visualization = request.data.get('visualization', 'table')
        config        = request.data.get('config', {})

        if not data_source:
            return Response({'error': 'data_source is required'}, status=status.HTTP_400_BAD_REQUEST)

        ds = get_data_source(data_source)
        if not ds:
            return Response({'error': f'Unknown data source: {data_source}'}, status=status.HTTP_400_BAD_REQUEST)

        ALLOW_ALL = {'wins', 'financial_years', 'business_units', 'public_holidays', 'skills', 'programmes', 'projects', 'resource_plans', 'sprint_forecast', 'onboarding', 'teams'}
        if not request.user.is_staff and not request.user.has_module_perms(ds['app_label']):
            if ds['app_label'] not in ALLOW_ALL:
                return Response(
                    {'error': f'You do not have permission to query {ds["label"]}.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        merged = dict(config)
        merged['visualization'] = visualization

        try:
            result = execute(merged, data_source)
        except DjangoValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            return _db_error_response(e, 'custom report preview')
        except Exception as e:
            return _unexpected_error_response(e, 'custom report preview')

        return Response(result)


class CustomReportExecuteView(APIView):
    """POST /api/v1/custom-reports/{pk}/execute/"""

    def post(self, request, pk):
        from .models import CustomReport
        from .data_sources import get_data_source
        from .query_engine import execute

        try:
            report = CustomReport.objects.get(pk=pk)
        except CustomReport.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not report.can_view(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        # Allow config override from request body (for live preview before save)
        config        = request.data.get('config') or report.config
        data_source   = request.data.get('data_source') or report.data_source
        visualization = request.data.get('visualization') or report.visualization

        if not data_source:
            return Response({'error': 'data_source is required'}, status=status.HTTP_400_BAD_REQUEST)

        ds = get_data_source(data_source)
        if not ds:
            return Response({'error': f'Unknown data source: {data_source}'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.is_staff and not request.user.has_module_perms(ds['app_label']):
            # Allow open sources
            if ds['app_label'] not in ('wins', 'financial_years'):
                return Response(
                    {'error': f'You do not have permission to query the {ds["label"]} data source.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        merged = dict(config)
        merged['visualization'] = visualization

        try:
            result = execute(merged, data_source)
        except DjangoValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            return _db_error_response(e, 'custom report execute')
        except Exception as e:
            return _unexpected_error_response(e, 'custom report execute')

        return Response(result)


class CustomReportExportView(APIView):
    """GET /api/v1/custom-reports/{pk}/export/?fmt=csv|xlsx"""

    def get(self, request, pk):
        from .models import CustomReport
        from .data_sources import get_data_source
        from .query_engine import execute, export_csv, export_xlsx

        try:
            report = CustomReport.objects.get(pk=pk)
        except CustomReport.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not report.can_view(request.user):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        viz = report.visualization
        if viz not in ('table', 'pivot', 'heatmap'):
            return Response(
                {'error': 'CSV/XLSX export is only available for Table, Pivot, and Heatmap visualizations.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ds = get_data_source(report.data_source)
        if not ds:
            return Response({'error': 'Invalid data source'}, status=status.HTTP_400_BAD_REQUEST)

        merged = dict(report.config)
        merged['visualization'] = viz

        try:
            result = execute(merged, report.data_source)
        except Exception as e:
            return _unexpected_error_response(e, 'custom report export')

        fmt      = request.query_params.get('fmt', 'csv').lower()
        filename = report.name.replace(' ', '_')[:50]

        if fmt == 'xlsx':
            content  = export_xlsx(result)
            response = HttpResponse(
                content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        else:
            content  = export_csv(result)
            response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

        return response


class CustomReportShareView(APIView):
    """
    GET    /api/v1/custom-reports/{pk}/share/            — list shares
    POST   /api/v1/custom-reports/{pk}/share/            — add/update share
    DELETE /api/v1/custom-reports/{pk}/share/{user_id}/  — remove share
    """

    def _get_owner_report(self, pk, user):
        from .models import CustomReport
        try:
            report = CustomReport.objects.get(pk=pk)
        except CustomReport.DoesNotExist:
            return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if report.owner_id != user.pk and not user.is_staff:
            return None, Response({'detail': 'Only the owner can manage sharing.'}, status=status.HTTP_403_FORBIDDEN)
        return report, None

    def get(self, request, pk):
        report, err = self._get_owner_report(pk, request.user)
        if err:
            return err
        from .serializers import CustomReportShareSerializer
        return Response(CustomReportShareSerializer(report.shares.select_related('user'), many=True).data)

    def post(self, request, pk):
        report, err = self._get_owner_report(pk, request.user)
        if err:
            return err
        from .models import CustomReportShare
        from .serializers import CustomReportShareWriteSerializer, CustomReportShareSerializer
        from django.contrib.auth import get_user_model
        ser = CustomReportShareWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        User = get_user_model()
        try:
            target = User.objects.get(pk=ser.validated_data['user_id'])
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        if target == request.user:
            return Response({'error': 'Cannot share with yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        share, _ = CustomReportShare.objects.update_or_create(
            report=report, user=target,
            defaults={'permission': ser.validated_data['permission'], 'shared_by': request.user},
        )
        if report.shares.exists() and not report.is_shared:
            report.is_shared = True
            report.save(update_fields=['is_shared'])
        return Response(CustomReportShareSerializer(share).data, status=status.HTTP_200_OK)

    def delete(self, request, pk, user_id):
        report, err = self._get_owner_report(pk, request.user)
        if err:
            return err
        from .models import CustomReportShare
        CustomReportShare.objects.filter(report=report, user_id=user_id).delete()
        if not report.shares.exists():
            report.is_shared = False
            report.save(update_fields=['is_shared'])
        return Response(status=status.HTTP_204_NO_CONTENT)
