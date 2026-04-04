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

from .models import PublicHoliday
from .serializers import PublicHolidaySerializer, PublicHolidayExportSerializer
from .services import PublicHolidayService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail
    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class PublicHolidayViewSet(viewsets.ViewSet):
    # GET /holidays/
    def list(self, request):
        """
        List all holidays.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = PublicHolidayService.list_holidays(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = PublicHolidaySerializer(result["results"], many=True)
            return Response(
                {
                    "results": serializer.data,
                    "pagination": {
                        "total_count": result["total_count"],
                        "total_pages": result["total_pages"],
                        "current_page": result["current_page"],
                        "page_size": result["page_size"],
                        "has_next": result["has_next"],
                        "has_previous": result["has_previous"],
                    },
                },
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            logger.exception("Database error in list: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /holidays/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """
        List all statistics associted with holidays
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = PublicHolidayService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("Database error in stats: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in stats: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /holidays/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        """
        List all options associated with holidays.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = PublicHolidayService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("Database error in options: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in options: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /holidays/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a holiday by specified id.
        """
        try:
            holiday = PublicHolidayService.get_holiday(pk)
            return Response(PublicHolidaySerializer(holiday).data, status=status.HTTP_200_OK)
        except PublicHoliday.DoesNotExist:
            logging.warning("Holiday %s does not exist", pk)
            return Response({'error': 'Holiday not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {'error': 'Invalid parameters.', 'details': _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("Database error in retrieve: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /holidays/
    def create(self, request):
        """
        Create a new holiday.
        """
        try:
            serializer = PublicHolidaySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            holiday = PublicHolidayService.create_holiday(serializer.validated_data)
            return Response(
                PublicHolidaySerializer(holiday).data,
                status=status.HTTP_201_CREATED,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {'error': 'Invalid parameters/values.', 'details': _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("Database error in create: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        """
        Update a holiday by specified id. Shared logic for PUT and PATCH.
        """
        try:
            try:
                instance = PublicHoliday.objects.get(pk=pk)
            except PublicHoliday.DoesNotExist:
                logging.warning("Public holiday %s does not exist", pk)
                return Response(
                    {
                        "error": "Holiday not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = PublicHolidaySerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            holiday = PublicHolidayService.update_holiday(pk, serializer.validated_data)
            return Response(
                PublicHolidaySerializer(holiday).data,
                status=status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in _perform_update: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in _perform_update: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in _perform_update: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /holidays/<id>/
    def update(self, request, pk=None):
        """
        Update a holiday by specified id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /holidays/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a holiday by specified id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /holidays/<id>/
    def destroy(self, request, pk=None):
        """
        Delete a holiday by specified id.
        """
        try:
            PublicHolidayService.delete_holiday(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PublicHoliday.DoesNotExist:
            logging.warning("Public holiday %s does not exist", pk)
            return Response({'error': 'Holiday not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in destroy: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in destroy: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in destroy: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /holidays/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specification for holidays.
        """
        specs = {
            'fields': [
                {'name': 'city', 'required': True, 'type': 'string',
                 'notes': "Must match an existing active location city exactly, e.g. 'London'."},
                {'name': 'country', 'required': True, 'type': 'string',
                 'notes': "Must match an existing active location country exactly, e.g. 'United Kingdom'."},
                {'name': 'date', 'required': True, 'type': 'date', 'format': 'YYYY-MM-DD'},
                {'name': 'name', 'required': True, 'type': 'string', 'max_length': 120,
                 'notes': "Name of the public holiday, e.g. 'Christmas Day'."},
            ],
            'notes': [
                'First row must be the header row.',
                'Date fields must be in YYYY-MM-DD format.',
                'The combination of city + country + date must be unique.',
                'Maximum 500 rows per import.',
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /holidays/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing holidays.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['city', 'country', 'date', 'name'])
        writer.writerow(['London', 'United Kingdom', '2025-12-25', 'Christmas Day'])
        writer.writerow(['London', 'United Kingdom', '2025-12-26', 'Boxing Day'])
        writer.writerow(['Manchester', 'United Kingdom', '2025-01-01', "New Year's Day"])
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="holidays_import_template.csv"'
        return response

    # POST /holidays/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for holidays.
        """
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = PublicHolidayService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /holidays/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of holidays. Returns JSON. UI handles CSV or PDF formats.
        """
        try:
            qs = PublicHoliday.objects.select_related('location').all()
            data = PublicHolidayExportSerializer(qs, many=True).data
            return Response({'count': len(data), 'results': data}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("Database error in export: %s", e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
