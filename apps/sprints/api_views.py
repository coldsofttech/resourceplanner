import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .engines import SprintEngineService
from .models import Sprint
from .serializers import (
    SprintSerializer,
    SprintSummarySerializer,
    SprintExportSerializer
)
from .services import SprintService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail
    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class SprintViewSet(viewsets.ViewSet):

    def get_permissions(self):
        if getattr(self, 'action', None) == 'active':
            return [IsAuthenticated()]
        return super().get_permissions()

    # GET /sprints/
    def list(self, request):
        """List all sprints. Supports filtering by fy_id, is_active, month, search."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = SprintService.list_sprints(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = SprintSerializer(result['results'], many=True)
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
            logger.exception("DB error in sprint list: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in sprint list: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /sprints/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        try:
            fy_id = request.query_params.get('fy_id')
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = SprintService.list_stats(fy_id=fy_id, fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in sprint stats: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in sprint stats: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /sprints/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(',') if fields_param else None
            result = SprintService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception('Unexpected error in sprint options: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /sprints/<id>/
    def retrieve(self, request, pk=None):
        try:
            sprint = SprintService.get_sprint(pk)
            return Response(SprintSerializer(sprint).data, status=status.HTTP_200_OK)
        except Sprint.DoesNotExist:
            return Response({'error': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, ValueError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception("DB error in sprint retrieve: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in sprint retrieve: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST /sprints/
    def create(self, request):
        try:
            serializer = SprintSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            sprint = SprintService.create_sprint(serializer.validated_data)
            return Response(SprintSerializer(sprint).data, status=status.HTTP_201_CREATED)
        except (DjangoValidationError, DRFValidationError) as e:
            return Response(
                {'error': 'Validation failed.', 'details': _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DB error in sprint create: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in sprint create: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _perform_update(self, request, pk, partial):
        try:
            try:
                instance = Sprint.objects.get(pk=pk)
            except Sprint.DoesNotExist:
                logging.warning("Sprint %s does not exist", pk)
                return Response(
                    {
                        "error": "Sprint not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = SprintSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            updated = SprintService.update_sprint(pk, serializer.validated_data)
            return Response(SprintSerializer(updated).data, status=status.HTTP_200_OK)
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

    # PUT /sprints/<id>/
    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    # PATCH /sprints/<id>/
    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    # DELETE /sprints/<id>/
    def destroy(self, request, pk=None):
        try:
            SprintService.delete_sprint(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Sprint.DoesNotExist:
            return Response({'error': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            logger.exception("DB error in sprint destroy: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in sprint destroy: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /sprints/active/
    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """Return the single active sprint (or 404 if none set)."""
        try:
            sprint = SprintService.get_active_sprint()
            if not sprint:
                return Response({'error': 'No active sprint found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(SprintSerializer(sprint).data, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in sprint active: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in sprint active: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /sprints/<id>/set-active/
    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """Mark a sprint as the active sprint; deactivates all others."""
        try:
            try:
                instance = Sprint.objects.get(pk=pk)
            except Sprint.DoesNotExist:
                logging.warning("Sprint %s does not exist", pk)
                return Response(
                    {
                        "error": "Sprint not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            sprint = SprintService.set_active(pk)
            return Response(SprintSerializer(sprint).data, status=status.HTTP_200_OK)
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
            logger.exception("DB error in set_active: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in set_active: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /sprints/summary/
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Lightweight list for navbar / dropdowns."""
        try:
            fy_id = request.query_params.get('fy_id')
            qs = SprintService.list_summary(fy_id=fy_id)
            return Response(SprintSummarySerializer(qs, many=True).data, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in sprint summary: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in sprint summary: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /sprints/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        try:
            fy_id = request.query_params.get('fy_id')
            qs = Sprint.objects.select_related('financial_year').order_by('financial_year', 'sprint_number')
            if fy_id:
                qs = qs.filter(financial_year_id=fy_id)
            data = SprintExportSerializer(qs, many=True).data
            return Response({'count': len(data), 'results': data}, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception('DB error in sprint export: %s', e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Unexpected error in sprint export: %s', e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /sprints/run-engine/
    @action(detail=False, methods=['post'], url_path='run-engine')
    def run_engine(self, request):
        """
        Auto-generate sprints for a financial year.
        Body: { "fy_id": <int>, "dry_run": <bool> }
        """
        fy_id = request.data.get('fy_id')
        dry_run = str(request.data.get('dry_run', 'false')).lower() == 'true'
        if not fy_id:
            return Response({'error': "'fy_id' is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = SprintEngineService.run(fy_id=int(fy_id), dry_run=dry_run)
            return Response(result, status=status.HTTP_200_OK)
        except (DjangoValidationError, ValueError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logger.exception("DB error in run_engine: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in run_engine: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /sprints/<id>/capacity/
    @action(detail=True, methods=['get'], url_path='capacity')
    def capacity(self, request, pk=None):
        """Capacity breakdown for all members in a specific sprint."""
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            from apps.sprint_capacity.services import SprintCapacityService
            from apps.sprint_capacity.serializers import SprintCapacitySerializer

            filters = request.query_params.dict()
            filters['sprint_id'] = pk

            result = SprintCapacityService.list_capacity(
                filters=filters,
                page=page,
                page_size=page_size,
            )
            serializer = SprintCapacitySerializer(result['results'], many=True)
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
            logger.exception("DB error in sprint capacity: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in sprint capacity: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
