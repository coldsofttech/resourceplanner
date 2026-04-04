import csv
import io
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .models import MemberLeave
from .serializers import MemberLeaveExportSerializer, MemberLeaveSerializer
from .services import MemberLeaveService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class MemberLeaveViewSet(viewsets.ViewSet):

    # GET /leaves/
    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = MemberLeaveService.list_leaves(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = MemberLeaveSerializer(result['results'], many=True)
            return Response({
                'results': serializer.data,
                'pagination': {
                    'total_count': result['total_count'],
                    'total_pages': result['total_pages'],
                    'current_page': result['current_page'],
                    'page_size': result['page_size'],
                    'has_next': result['has_next'],
                    'has_previous': result['has_previous'],
                },
            }, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("Database error in list: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /leaves/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = MemberLeaveService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("Database error in stats: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in stats: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /leaves/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = MemberLeaveService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Unexpected error in option_choices: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /leaves/<id>/
    def retrieve(self, request, pk=None):
        try:
            leave = MemberLeaveService.get_leave(pk)
            return Response(MemberLeaveSerializer(leave).data, status=status.HTTP_200_OK)
        except MemberLeave.DoesNotExist:
            logging.warning("Leave %s does not exist", pk)
            return Response({'error': 'Leave record not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({'error': 'Invalid parameters.', 'details': _validation_details(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DB error in retrieve: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST /leaves/
    def create(self, request):
        try:
            serializer = MemberLeaveSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            leave = MemberLeaveService.create_leave(serializer.validated_data)
            return Response(MemberLeaveSerializer(leave).data, status=status.HTTP_201_CREATED)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in create: %s", e)
            return Response({'error': 'Invalid parameters.', 'details': _validation_details(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DB error in create: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _perform_update(self, request, pk, partial):
        try:
            try:
                instance = MemberLeave.objects.get(pk=pk)
            except MemberLeave.DoesNotExist:
                logging.warning("Leave %s does not exist", pk)
                return Response(
                    {
                        "error": "Leave not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = MemberLeaveSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated = MemberLeaveService.update_leave(pk, serializer.validated_data)
            return Response(MemberLeaveSerializer(updated).data, status=status.HTTP_200_OK)
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

    # PUT /leaves/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /leaves/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /leaves/<id>/
    def destroy(self, request, pk=None):
        try:
            MemberLeaveService.delete_leave(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except MemberLeave.DoesNotExist:
            logging.warning("Leave %s does not exist", pk)
            return Response({'error': 'Leave record not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, ValueError) as e:
            logging.warning("Validation error in destroy: %s", e)
            return Response({'error': 'Invalid parameters.', 'details': _validation_details(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DB error in destroy: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in destroy: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /leaves/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        try:
            qs = MemberLeave.objects.select_related('member', 'member__location').all()
            data = MemberLeaveExportSerializer(qs, many=True).data
            return Response({'count': len(data), 'results': data}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("DB error in export: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /leaves/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        specs = {
            'fields': [
                {'name': 'email_address', 'required': True, 'type': 'string',
                 'description': 'Email address of an active TeamMember — must match exactly'},
                {'name': 'start_date', 'required': True, 'type': 'date (YYYY-MM-DD)'},
                {'name': 'end_date', 'required': True, 'type': 'date (YYYY-MM-DD)'},
                {'name': 'is_half_day', 'required': False, 'type': 'boolean',
                 'allowed_values': ['true', 'false'], 'default': 'false'},
                {'name': 'half_day_period', 'required': False, 'type': 'string',
                 'allowed_values': ['AM', 'PM'],
                 'description': 'Required when is_half_day=true'},
                {'name': 'note', 'required': False, 'type': 'string'},
            ],
            'notes': [
                'First row must be the header.',
                'email_address must exactly match the stored value for an active team member (case-insensitive).',
                'is_half_day=true requires start_date == end_date.',
                'Overlapping date ranges for the same member are rejected.',
                'Days are auto-calculated (excludes weekends and public holidays for the member\'s location).',
                'Maximum 500 rows per import.',
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /leaves/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['email_address', 'start_date', 'end_date', 'is_half_day', 'half_day_period', 'note'])
        writer.writerow(['alice.smith@example.com', '2025-08-25', '2025-08-29', 'false', '', 'Summer break'])
        writer.writerow(['bob.jones@example.com', '2025-09-01', '2025-09-01', 'true', 'AM', 'Dentist appointment'])
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="leaves_import_template.csv"'
        return response

    # POST /leaves/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = MemberLeaveService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
