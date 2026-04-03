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

from .models import TeamRole
from .serializers import TeamRoleSerializer, TeamRoleExportSerializer
from .services import TeamRoleService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class TeamRoleViewSet(viewsets.ViewSet):
    # GET /roles/
    def list(self, request):
        """
        List all team roles.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = TeamRoleService.list_roles(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = TeamRoleSerializer(result["results"], many=True)
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

    # GET /roles/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """
        List all statistics associated with team roles.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = TeamRoleService.list_stats(fields=fields)
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

    # GET /roles/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        """
        List all options associated with team roles.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = TeamRoleService.list_options(fields=fields)
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

    # GET /roles/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single team role by specified role id.
        """
        try:
            role = TeamRoleService.get_role(pk)
            serializer = TeamRoleSerializer(role)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except TeamRole.DoesNotExist:
            logging.warning("TeamRole %s does not exist", pk)
            return Response(
                {
                    "error": "Role not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in retrieve: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e)
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

    # POST /roles/
    def create(self, request):
        """
        Create a new team role.
        """
        try:
            serializer = TeamRoleSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            role = TeamRoleService.create_role(serializer.validated_data)
            return Response(
                TeamRoleSerializer(role).data,
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
        Update a team role by specified role id. Shared logic for PUT and PATCH.
        """
        try:
            try:
                instance = TeamRole.objects.get(pk=pk)
            except TeamRole.DoesNotExist:
                logging.warning("TeamRole %s does not exist", pk)
                return Response(
                    {
                        "error": "Role not found."
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = TeamRoleSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            role = TeamRoleService.update_role(pk, serializer.validated_data)
            return Response(
                TeamRoleSerializer(role).data,
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

    # PUT /roles/<id>/
    def update(self, request, pk=None):
        """
        Update a team role by specified role id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /roles/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a team role by specified role id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /roles/<id>/
    def destroy(self, request, pk=None):
        """
        Delete a team role by specified role id.
        """
        try:
            TeamRoleService.delete_role(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TeamRole.DoesNotExist:
            logging.warning("TeamRole %s does not exist", pk)
            return Response(
                {
                    "error": "Role not found."
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

    # GET /roles/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specifications for team roles.
        """
        specs = {
            "fields": [
                {"name": "role", "required": True, "type": "string", "max_length": 100},
                {
                    "name": "is_active", "required": False, "type": "boolean",
                    "allowed_values": ["true", "false"], "default": "true"
                },
                {
                    "name": "is_assignable", "required": False, "type": "boolean",
                    "allowed_values": ["true", "false"], "default": "false"
                },
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
            ]
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /roles/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing team roles.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["role", "is_active", "is_assignable"]) # header
        writer.writerow(["Senior Engineer", "true", "true"]) # sample row

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="roles_import_template.csv"'
        return response

    # POST /roles/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for team roles.
        """
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = TeamRoleService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except DjangoValidationError as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /roles/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of team roles. Returns JSON. UI to handle CSV or PDF formats.
        """
        try:
            qs = TeamRole.objects.all()
            data = TeamRoleExportSerializer(qs, many=True).data
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
