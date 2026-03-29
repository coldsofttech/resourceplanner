import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import DeliveryTeamSerializer, DeliveryTeamExportSerializer
from .services import DeliveryTeamService

logger = logging.getLogger(__name__)


class DeliveryTeamViewSet(viewsets.ViewSet):
    # GET /delivery-teams/
    def list(self, request):
        """
        List all delivery teams.
        """
        try:
            teams = DeliveryTeamService.list_teams(filters=request.query_params)
            serializer = DeliveryTeamSerializer(teams, many=True)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            logging.exception("Database error in list_teams: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_teams: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /delivery-teams/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single delivery team by specified team id.
        """
        try:
            team = DeliveryTeamService.get_team(pk)
            serializer = DeliveryTeamSerializer(team)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in get_team: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in get_team: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in get_team: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /delivery-teams/
    def create(self, request):
        """
        Create a new delivery team.
        """
        try:
            serializer = DeliveryTeamSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            team = DeliveryTeamService.create_team(serializer.validated_data)
            return Response(
                DeliveryTeamSerializer(team).data,
                status=status.HTTP_201_CREATED,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in create_team: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in create_team: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create_team: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        """
        Update a delivery team by specified team id.
        """
        try:
            serializer = DeliveryTeamSerializer(data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            team = DeliveryTeamService.update_team(pk, serializer.validated_data)
            return Response(
                DeliveryTeamSerializer(team).data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in update_team: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in update_team: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in update_team: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /delivery-teams/<id>/
    def update(self, request, pk=None):
        """
        Update a delivery team by specified team id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /delivery-teams/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a delivery team by specified team id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /delivery-teams/<id>/
    def destroy(self, request, pk=None):
        """
        Delete a delivery team by specified team id.
        """
        try:
            DeliveryTeamService.delete_team(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in delete_team: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in delete_team: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in delete_team: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /delivery-teams/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specifications for delivery teams.
        """
        specs = {
            "fields": [
                {"name": "name", "required": True, "type": "string", "max_length": 120},
                {"name": "description", "required": False, "type": "string"},
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

    # GET /delivery-teams/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing delivery teams.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["name", "description", "is_active"])  # header
        writer.writerow(["Team Alpha", "Example description", "true"])  # sample row

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="delivery_teams_import_template.csv"'
        return response

    # POST /delivery-teams/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for delivery teams.
        """
        try:
            results = DeliveryTeamService.bulk_import(request)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /delivery-teams/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of delivery teams. Returns JSON. UI to handle CSV or PDF formats.
        """
        try:
            teams = DeliveryTeamService.list_teams(filters=request.query_params)
            data = DeliveryTeamExportSerializer(teams, many=True).data
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
