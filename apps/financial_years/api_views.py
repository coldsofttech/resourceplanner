import csv
import io
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .models import FinancialYear
from .serializers import (
    FinancialYearSerializer,
    FinancialYearSummarySerializer,
    FinancialYearExportSerializer,
)
from .services import FinancialYearService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class FinancialYearViewSet(viewsets.ViewSet):

    # GET /fy/
    def list(self, request):
        """Paginated list of all financial years."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = FinancialYearService.list_financial_years(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = FinancialYearSerializer(result['results'], many=True)
            return Response(
                {
                    'results': serializer.data,
                    'pagination': {
                        'total_count': result['total_count'],
                        'total_pages': result['total_pages'],
                        'current_page': result['current_page'],
                        'page_size': result['page_size'],
                        'has_next': result['has_next'],
                        'has_previous': result['has_previous'],
                    },
                },
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            logger.exception('DB error in fy list: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy list: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = FinancialYearService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in fy stats: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy stats: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = FinancialYearService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception('Unexpected error in fy options: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/<pk>/
    def retrieve(self, request, pk=None):
        try:
            fy = FinancialYearService.get_financial_year(pk)
            return Response(FinancialYearSerializer(fy).data, status=status.HTTP_200_OK)
        except FinancialYear.DoesNotExist:
            logging.warning("Leave %s does not exist", pk)
            return Response({'error': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {'error': 'Invalid parameters.', 'details': _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception('DB error in fy retrieve: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy retrieve: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /fy/
    def create(self, request):
        try:
            serializer = FinancialYearSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            fy = FinancialYearService.create_financial_year(serializer.validated_data)
            return Response(FinancialYearSerializer(fy).data, status=status.HTTP_201_CREATED)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in create: %s", e)
            return Response(
                {'error': 'Validation failed.', 'details': _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Unexpected error in fy create: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial):
        try:
            try:
                instance = FinancialYear.objects.get(pk=pk)
            except FinancialYear.DoesNotExist:
                logging.warning("Financial year %s does not exist", pk)
                return Response(
                    {
                        "error": "Financial year not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = FinancialYearSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated = FinancialYearService.update_financial_year(pk, serializer.validated_data)
            return Response(FinancialYearSerializer(updated).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in _perform_update: %s", e)
            return Response({'error': 'Invalid parameters.', 'details': _validation_details(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DB error in update: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in update: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # PUT /fy/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /fy/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /fy/<pk>/
    def destroy(self, request, pk=None):
        try:
            FinancialYearService.delete_financial_year(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except FinancialYear.DoesNotExist:
            logging.warning("Financial year %s does not exist", pk)
            return Response({'error': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Unexpected error in fy destroy: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/active/
    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """Returns the currently active financial year, or 404 if none set."""
        try:
            fy = FinancialYearService.get_active_financial_year()
            if fy is None:
                return Response({'error': 'No active financial year.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(FinancialYearSerializer(fy).data, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in fy active: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy active: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /fy/<id>/set-active/
    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        try:
            try:
                instance = FinancialYear.objects.get(pk=pk)
            except FinancialYear.DoesNotExist:
                logging.warning("Financial year %s does not exist", pk)
                return Response(
                    {
                        "error": "Financial year not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # serializer = FinancialYearSerializer(data=request.data)
            # serializer.is_valid(raise_exception=True)
            fy = FinancialYearService.set_active(pk)
            return Response(FinancialYearSerializer(fy).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in set_active: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in set_active: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in set_active: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/summary/
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Compact list used by the navbar dropdown and cross-module selects.
        No pagination — financial years are few in number.
        """
        try:
            qs = FinancialYearService.list_summary()
            return Response(FinancialYearSummarySerializer(qs, many=True).data, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in fy summary: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy summary: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """Returns JSON; UI (JS) handles CSV / PDF rendering."""
        try:
            qs = FinancialYear.objects.all().order_by('-start_date')
            data = FinancialYearExportSerializer(qs, many=True).data
            return Response({'count': len(data), 'results': data}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in fy export: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy export: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /fy/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        specs = {
            'fields': [
                {'name': 'start_date', 'required': True, 'type': 'date', 'format': 'YYYY-MM-DD'},
                {'name': 'end_date', 'required': True, 'type': 'date', 'format': 'YYYY-MM-DD'},
                {'name': 'notes', 'required': False, 'type': 'string'},
            ],
            'notes': [
                'First row must be the header.',
                'Dates must be in YYYY-MM-DD format.',
                'Boolean fields accept: true / false (case-insensitive).',
                'Maximum 500 rows per import.',
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /fy/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['start_date', 'end_date', 'notes'])
        writer.writerow(['2024-04-01', '2025-03-31', 'Current financial year'])
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="fys_import_template.csv"'
        return response

    # POST /fy/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import financial years from a CSV file.
        Pass ?validate=true for a dry run (no DB writes).
        """
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = FinancialYearService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logger.warning('Validation error in fy bulk_import: %s', e)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception('Unexpected error in fy bulk_import: %s', e)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
