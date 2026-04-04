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

from .models import OfficeLocation
from .serializers import OfficeLocationSerializer, OfficeLocationExportSerializer
from .services import OfficeLocationService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class OfficeLocationViewSet(viewsets.ViewSet):
    # GET /locations/
    def list(self, request):
        """
        List all office locations.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = OfficeLocationService.list_locations(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = OfficeLocationSerializer(result["results"], many=True)
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

    # GET /locations/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """
        List all statistics associated with office locations.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = OfficeLocationService.list_stats(fields=fields)
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

    # GET /locations/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        """
        List all options associated with delivery teams.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = OfficeLocationService.list_options(fields=fields)
            return Response(result, status=status.HTTP_200_OK)
        except DatabaseError as e:
            logging.exception("Database error in option_choices: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in option_choices: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /locations/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single location by specified id.
        """
        try:
            location = OfficeLocationService.get_location(pk)
            serializer = OfficeLocationSerializer(location)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except OfficeLocation.DoesNotExist:
            logging.warning("Location %s does not exist", pk)
            return Response(
                {
                    "error": "Location not found."
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

    # POST /locations/
    def create(self, request):
        """
        Create a new office location.
        """
        try:
            serializer = OfficeLocationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            location = OfficeLocationService.create_location(serializer.validated_data)
            return Response(
                OfficeLocationSerializer(location).data,
                status=status.HTTP_201_CREATED,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in create: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in create: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        """
        Update a office location by specified id. Shared logic for PUT and PATCH.
        """
        try:
            try:
                instance = OfficeLocation.objects.get(pk=pk)
            except OfficeLocation.DoesNotExist:
                logging.warning("Location %s does not exist", pk)
                return Response(
                    {
                        "error": "Location not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = OfficeLocationSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            location = OfficeLocationService.update_location(pk, serializer.validated_data)
            return Response(
                OfficeLocationSerializer(location).data,
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

    # PUT /locations/<id>/
    def update(self, request, pk=None):
        """
        Update a office location by specified id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /locations/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a office location by specified id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /locations/<id>/
    def destroy(self, request, pk=None):
        """
        Delete an office location by specified id.
        """
        try:
            OfficeLocationService.delete_location(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except OfficeLocation.DoesNotExist:
            logging.warning("Location %s does not exist", pk)
            return Response(
                {
                    "error": "Location not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
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

    # GET /locations/<id>/members/
    @action(detail=True, methods=['get'], url_path='members')
    def list_members(self, request, pk=None):
        """
        List all members associated with the location
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            include = request.query_params.get('include', '')
        except (ValueError, TypeError):
            page, page_size, include = 1, 20, ''

        try:
            result = OfficeLocationService.list_members(
                location_id=pk,
                page=page,
                page_size=page_size,
                include_inactive=include == "inactive",
            )
            from apps.team_members.serializers import TeamMemberSerializer
            serializer = TeamMemberSerializer(result["results"], many=True)
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
            logging.exception("Database error in list_members: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_members: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /locations/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specifications for office locations.
        """
        specs = {
            "fields": [
                {"name": "city", "required": True, "type": "string", "max_length": 100},
                {"name": "country", "required": True, "type": "string", "max_length": 100},
                {
                    "name": "is_active", "required": False, "type": "boolean",
                    "allowed_values": ["true", "false"], "default": "true"
                },
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
            ]
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /locations/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing office locations.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["city", "country", "is_active"])  # header
        writer.writerow(["London", "United Kingdom", "true"])  # sample row

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="locations_import_template.csv"'
        return response

    # POST /locations/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for office locations.
        """
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = OfficeLocationService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /locations/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of office locations. Returns JSON. UI handles CSV or PDF formats.
        """
        try:
            qs = OfficeLocation.objects.all()
            data = OfficeLocationExportSerializer(qs, many=True).data
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
