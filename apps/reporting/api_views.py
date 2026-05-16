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
    MappingUpsertSerializer,
    ProgrammeCategoryMappingSerializer,
    ReportSerializer,
)
from .services import (
    REPORT_REGISTRY,
    DemandCapacityConfigService,
    DemandCapacityService,
    ReportService,
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
