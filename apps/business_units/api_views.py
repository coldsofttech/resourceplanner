import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .models import BusinessUnit
from .serializers import BusinessUnitSerializer, BusinessUnitOptionSerializer
from .services import BusinessUnitService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail
    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class BusinessUnitViewSet(viewsets.ViewSet):

    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20
        try:
            result = BusinessUnitService.list_business_units(
                filters=request.query_params, page=page, page_size=page_size
            )
            return Response({
                'results': BusinessUnitSerializer(result['results'], many=True).data,
                'pagination': {
                    'total_count': result['total_count'],
                    'total_pages': result['total_pages'],
                    'current_page': result['current_page'],
                    'page_size': result['page_size'],
                    'has_next': result['has_next'],
                    'has_previous': result['has_previous'],
                },
            })
        except DatabaseError as e:
            logger.exception('DB error in list: %s', e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Unexpected error in list: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        try:
            return Response(BusinessUnitService.list_stats())
        except Exception as e:
            logger.exception('Error in stats: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        try:
            return Response(BusinessUnitService.list_options())
        except Exception as e:
            logger.exception('Error in options: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            bu = BusinessUnitService.get_business_unit(pk)
            return Response(BusinessUnitSerializer(bu).data)
        except BusinessUnit.DoesNotExist:
            return Response({'error': 'Business unit not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception('Error in retrieve: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        try:
            serializer = BusinessUnitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            bu = BusinessUnitService.create_business_unit(serializer.validated_data)
            return Response(BusinessUnitSerializer(bu).data, status=status.HTTP_201_CREATED)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({'error': 'Validation error.', 'details': _validation_details(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception('DB error in create: %s', e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Error in create: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _perform_update(self, request, pk, partial):
        try:
            try:
                instance = BusinessUnit.objects.get(pk=pk)
            except BusinessUnit.DoesNotExist:
                return Response({'error': 'Business unit not found.'}, status=status.HTTP_404_NOT_FOUND)
            serializer = BusinessUnitSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            bu = BusinessUnitService.update_business_unit(pk, serializer.validated_data)
            return Response(BusinessUnitSerializer(bu).data)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({'error': 'Validation error.', 'details': _validation_details(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception('DB error in update: %s', e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Error in update: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, pk=None):
        return self._perform_update(request, pk, partial=False)

    def partial_update(self, request, pk=None):
        return self._perform_update(request, pk, partial=True)

    def destroy(self, request, pk=None):
        try:
            BusinessUnitService.delete_business_unit(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except BusinessUnit.DoesNotExist:
            return Response({'error': 'Business unit not found.'}, status=status.HTTP_404_NOT_FOUND)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response({'error': 'Validation error.', 'details': _validation_details(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.exception('DB error in destroy: %s', e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception('Error in destroy: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
