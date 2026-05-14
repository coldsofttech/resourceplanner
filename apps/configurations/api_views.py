import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .models import Configuration
from .serializers import ConfigurationSerializer, ConfigurationExportSerializer
from .services import ConfigurationService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class ConfigurationViewSet(viewsets.ViewSet):
    # GET /configurations/
    def list(self, request):
        """
        List all configurations.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = ConfigurationService.list_configurations(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = ConfigurationSerializer(result["results"], many=True)
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
            logging.exception("Database error in list: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /configurations/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """
        List all statistics associated with configurations.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = ConfigurationService.list_stats(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logging.exception("Database error in stats: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in stats: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /configurations/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single configuration by specified config id.
        """
        try:
            config = ConfigurationService.get_configuration(pk)
            serializer = ConfigurationSerializer(config)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except Configuration.DoesNotExist:
            logging.warning("Configuration %s does not exist", pk)
            return Response(
                {
                    "error": "Configuration not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in retrieve: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in retrieve: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in retrieve: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /configurations/by_code/<code>
    @action(detail=False, methods=['get'], url_path='by_code')
    def by_code(self, request):
        """
        Retrieve a single configuration by specified config code.
        """
        code = request.query_params.get('code', '').strip().upper()
        if not code:
            return Response(
                {
                    "error": "Provide ?code=CONFIG_CODE in the query string.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            config = ConfigurationService.get_configuration_by_code(code)
            serializer = ConfigurationSerializer(config)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except Configuration.DoesNotExist:
            logging.warning("Configuration %s does not exist", code)
            return Response(
                {
                    "error": "Configuration not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in by_code: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in by_code: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in by_code: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /configurations/factory_default/<code>
    @action(detail=False, methods=['get'], url_path='system_default')
    def factory_default(self, request):
        """
        Retrieve a factory default configuration by specified config code.
        """
        code = request.query_params.get('code', '').strip().upper()
        if not code:
            return Response(
                {
                    "error": "Provide ?code=CONFIG_CODE in the query string.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            default_value = ConfigurationService.get_default_configuration_value(code)
            if default_value is None:
                return Response(
                    {
                        "error": "No system default registered for this code."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {
                    "code": code,
                    "default_value": default_value
                },
                status=status.HTTP_200_OK
            )
        except Configuration.DoesNotExist:
            logging.warning("Configuration %s does not exist", code)
            return Response(
                {
                    "error": "Configuration not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in factory_default: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in factory_default: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in factory_default: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        """
        Update a configuration by specified config id. Shared logic for PUT and PATCH.
        For secret configs an empty/missing value is treated as a no-op (keep existing).
        """
        value = request.data.get('value')

        try:
            try:
                instance = Configuration.objects.get(pk=pk)
            except Configuration.DoesNotExist:
                logging.warning("Configuration %s does not exist", pk)
                return Response(
                    {
                        "error": "Configuration not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Non-secret configs require value to be provided
            if value is None and not instance.is_secret:
                return Response(
                    {
                        "error": "Only the 'value' field can be updated."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Secret with no value provided → return current state unchanged
            if value is None and instance.is_secret:
                return Response(
                    ConfigurationSerializer(instance).data,
                    status=status.HTTP_200_OK,
                )

            serializer = ConfigurationSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            config = ConfigurationService.update_configuration(pk, serializer.validated_data.get('value'))
            return Response(
                ConfigurationSerializer(config).data,
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

    # PATCH /configurations/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a configuration by specified config id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # GET /configurations/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of configurations. Returns JSON. UI handles CSV or PDF formats.
        """
        try:
            qs = Configuration.objects.all()
            data = ConfigurationExportSerializer(qs, many=True).data
            return Response(
                {
                    "count": len(data),
                    "results": data,
                },
                status=status.HTTP_200_OK
            )
        except DatabaseError as e:
            logging.exception("Database error in export: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in export: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /configurations/<id>/reset/
    @action(detail=True, methods=['post'], url_path='reset')
    def reset(self, request, pk=None):
        """
        Reset to default configuration.
        """
        try:
            try:
                instance = Configuration.objects.get(pk=pk)
            except Configuration.DoesNotExist:
                logging.warning("Configuration %s does not exist", pk)
                return Response(
                    {
                        "error": "Configuration not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            config = ConfigurationService.reset_to_default(pk)
            return Response(
                ConfigurationSerializer(config).data,
                status=status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in reset: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in reset: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in reset: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
