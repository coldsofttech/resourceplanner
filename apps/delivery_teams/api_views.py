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

from .models import DeliveryTeam
from .serializers import DeliveryTeamSerializer, DeliveryTeamExportSerializer
from .services import DeliveryTeamService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class DeliveryTeamViewSet(viewsets.ViewSet):
    # GET /delivery-teams/
    def list(self, request):
        """
        List all delivery teams.
        """
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = DeliveryTeamService.list_teams(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = DeliveryTeamSerializer(result["results"], many=True)
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

    # GET /delivery-teams/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def statistics(self, request):
        """
        List all statistics associated with delivery teams.
        """
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = DeliveryTeamService.list_stats(fields=fields)
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

    # GET /delivery-teams/options/
    @action(detail=False, methods=["get"], url_path="options")
    def option_choices(self, request):
        """
        List all options associated with delivery teams.
        """
        try:
            fields_param = request.query_params.get("fields")
            fields = fields_param.split(",") if fields_param else None
            result = DeliveryTeamService.list_options(fields=fields)
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
        except DeliveryTeam.DoesNotExist:
            logging.warning("Delivery team %s does not exist", pk)
            return Response(
                {"error": "Team not found."},
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
        Update a delivery team by specified team id. Shared logic for PUT and PATCH.
        """
        try:
            try:
                instance = DeliveryTeam.objects.get(pk=pk)
            except DeliveryTeam.DoesNotExist:
                logging.warning("Delivery team %s does not exist", pk)
                return Response(
                    {"error": "Team not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = DeliveryTeamSerializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            team = DeliveryTeamService.update_team(pk, serializer.validated_data)
            return Response(
                DeliveryTeamSerializer(team).data,
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
        except DeliveryTeam.DoesNotExist:
            logging.warning("Delivery team %s does not exist", pk)
            return Response(
                {"error": "Team not found."},
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

    # GET /delivery-teams/<id>/members/
    @action(detail=True, methods=["get"], url_path="members")
    def list_members(self, request, pk=None):
        """
        List all members associated with the team
        """
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
            include = request.query_params.get("include", "")
        except (ValueError, TypeError):
            page, page_size, include = 1, 20, ""

        try:
            result = DeliveryTeamService.list_members(
                team_id=pk,
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

    # GET /delivery-teams/<id>/projects/
    @action(detail=True, methods=["get"], url_path="projects")
    def list_projects(self, request, pk=None):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = DeliveryTeamService.list_projects(
                team_id=pk,
                page=page,
                page_size=page_size,
            )
            from apps.projects.serializers import ProjectSerializer

            serializer = ProjectSerializer(result["results"], many=True)
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
            logging.exception("Database error in list_projects: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_projects: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /delivery-teams/<id>/leaves
    @action(detail=True, methods=["get"], url_path="leaves")
    def list_leaves(self, request, pk=None):
        """
        List all leaves for active members within the specified team.
        """
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
            include = request.query_params.get("include", "")
        except (ValueError, TypeError):
            page, page_size, include = 1, 20, ""

        try:
            result = DeliveryTeamService.list_leaves(
                team_id=pk,
                page=page,
                page_size=page_size,
                include_past=include == "past",
            )
            from apps.member_leaves.serializers import MemberLeaveSerializer

            serializer = MemberLeaveSerializer(result["results"], many=True)
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
        except DeliveryTeam.DoesNotExist:
            return Response(
                {"error": "Delivery team not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DatabaseError as e:
            logger.exception("Database error in list_leaves: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_leaves: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /delivery-teams/<id>/assign-member/
    @action(detail=True, methods=["post"], url_path="assign-member")
    def assign_member(self, request, pk=None):
        """
        Assign a member to this team.
        - Assignable roles: replaces existing assignment and records history.
        - Shareable roles: adds to existing assignments.
        """
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from apps.team_members.services import TeamMemberService

        member_id = request.data.get('member_id')
        if not member_id:
            return Response({"error": "member_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            DeliveryTeam.objects.get(pk=pk)
        except DeliveryTeam.DoesNotExist:
            return Response({"error": "Team not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            member = TeamMemberService.assign_team(int(member_id), int(pk))
            from apps.team_members.serializers import TeamMemberSerializer
            return Response(TeamMemberSerializer(member).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {"error": "Invalid parameters/values.", "details": _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in assign_member: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in assign_member: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # DELETE /delivery-teams/<id>/unassign-member/<member_id>/
    @action(detail=True, methods=["delete"], url_path=r"unassign-member/(?P<member_id>[0-9]+)")
    def unassign_member(self, request, pk=None, member_id=None):
        """Remove a member's assignment from this team."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from apps.team_members.services import TeamMemberService

        try:
            DeliveryTeam.objects.get(pk=pk)
        except DeliveryTeam.DoesNotExist:
            return Response({"error": "Team not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            member = TeamMemberService.unassign_team(int(member_id), int(pk))
            from apps.team_members.serializers import TeamMemberSerializer
            return Response(TeamMemberSerializer(member).data, status=status.HTTP_200_OK)
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            return Response(
                {"error": "Invalid parameters/values.", "details": _validation_details(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in unassign_member: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in unassign_member: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /delivery-teams/import/specifications/
    @action(detail=False, methods=["get"], url_path="import/specifications")
    def import_specifications(self, request):
        """
        Import specifications for delivery teams.
        """
        specs = {
            "fields": [
                {"name": "name", "required": True, "type": "string", "max_length": 120},
                {"name": "description", "required": False, "type": "string"},
                {
                    "name": "is_active",
                    "required": False,
                    "type": "boolean",
                    "allowed_values": ["true", "false"],
                    "default": "true",
                },
            ],
            "notes": [
                "First row must be the header.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Maximum 500 rows per import.",
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /delivery-teams/import/sample/
    @action(detail=False, methods=["get"], url_path="import/sample")
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
        response["Content-Disposition"] = (
            'attachment; filename="delivery_teams_import_template.csv"'
        )
        return response

    # POST /delivery-teams/import/
    @action(detail=False, methods=["post"], url_path="import")
    def bulk_import(self, request):
        """
        Bulk import for delivery teams.
        """
        dry_run = request.query_params.get("validate", "false").lower() == "true"
        try:
            results = DeliveryTeamService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # GET /delivery-teams/export/
    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """
        Export of delivery teams. Returns JSON. UI handles CSV or PDF formats.
        """
        try:
            qs = DeliveryTeam.objects.all()
            data = DeliveryTeamExportSerializer(qs, many=True).data
            return Response(
                {
                    "count": len(data),
                    "results": data,
                },
                status=status.HTTP_200_OK,
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
