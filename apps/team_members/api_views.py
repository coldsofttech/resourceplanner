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

from .models import TeamMember
from .serializers import TeamMemberSerializer, TeamMemberExportSerializer, MoveTeamSerializer, \
    TeamMemberHistorySerializer
from .services import TeamMemberService

logger = logging.getLogger(__name__)


def _validation_details(e):
    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages


class TeamMemberViewSet(viewsets.ViewSet):
    # GET /team-members/
    def list(self, request):
        """
        List all team members.
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = TeamMemberService.list_members(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
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

    # GET /team-members/stats/
    @action(detail=False, methods=['get'], url_path='stats')
    def statistics(self, request):
        """
        List all statistics associated with team members.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = TeamMemberService.list_stats(fields=fields)
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

    # GET /team-members/options/
    @action(detail=False, methods=['get'], url_path='options')
    def option_choices(self, request):
        """
        List all options associated with team members.
        """
        try:
            fields_param = request.query_params.get('fields')
            fields = fields_param.split(",") if fields_param else None
            result = TeamMemberService.list_options(fields=fields)
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

    # GET /team-members/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single team member by specified id.
        """
        try:
            member = TeamMemberService.get_member(pk)
            serializer = TeamMemberSerializer(member)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except TeamMember.DoesNotExist:
            logging.warning("Team member %s does not exist", pk)
            return Response(
                {
                    "error": "Member not found."
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

    # POST /team-members/
    def create(self, request):
        """
        Create a new team member.
        """
        try:
            serializer = TeamMemberSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            member = TeamMemberService.create_member(serializer.validated_data)
            return Response(
                TeamMemberSerializer(member).data,
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
        Update a team member by specified id. Shared logic for PUT and PATCH.
        """
        try:
            try:
                instance = TeamMember.objects.get(pk=pk)
            except TeamMember.DoesNotExist:
                logging.warning("Team member %s does not exist", pk)
                return Response(
                    {
                        "error": "Member not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = TeamMemberSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            member = TeamMemberService.update_member(pk, serializer.validated_data)
            return Response(
                TeamMemberSerializer(member).data,
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

    # PUT /team-members/<id>/
    def update(self, request, pk=None):
        """
        Update a team member by specified id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /team-members/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a team member by specified id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /team-members/<id>/
    def destroy(self, request, pk=None):
        """
        Delete a team member by specified id.
        """
        try:
            TeamMemberService.delete_member(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TeamMember.DoesNotExist:
            logging.warning("Team member %s does not exist", pk)
            return Response(
                {
                    "error": "Member not found."
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

    # GET /team-members/<id>/leaves
    @action(detail=True, methods=['get'], url_path='leaves')
    def list_leaves(self, request, pk=None):
        """
        List all leaves associated with the member
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            include = request.query_params.get('include', '')
        except (ValueError, TypeError):
            page, page_size, include = 1, 20, ''

        try:
            result = TeamMemberService.list_leaves(
                member_id=pk,
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
        except TeamMember.DoesNotExist:
            return Response(
                {'error': 'Team member not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DatabaseError as e:
            logging.exception("Database error in list_leaves: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_leaves: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /team-members/<id>/move-team
    @action(detail=True, methods=['post'], url_path='move-team')
    def move_team(self, request, pk=None):
        """
        Move member from one to team to another.
        """
        try:
            try:
                instance = TeamMember.objects.get(pk=pk)
            except TeamMember.DoesNotExist:
                logging.warning("Team member %s does not exist", pk)
                return Response(
                    {
                        "error": "Member not found."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = MoveTeamSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            member = TeamMemberService.move_team(pk, serializer.validated_data)
            return Response(
                TeamMemberSerializer(member).data,
                status=status.HTTP_200_OK,
            )
        except (DjangoValidationError, DRFValidationError, ValueError) as e:
            logging.warning("Validation error in move_team: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": _validation_details(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in move_team: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in move_team: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /team-members/<id>/history/
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        List the history associated with team member
        """
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = TeamMemberService.history(
                member_id=pk,
                page=page,
                page_size=page_size,
            )
            serializer = TeamMemberHistorySerializer(result["results"], many=True)
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
            logging.exception("Database error in history: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in history: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /team-members/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specifications for team members.
        """
        specs = {
            "fields": [
                {"name": "first_name", "required": True, "type": "string", "max_length": 80},
                {"name": "last_name", "required": True, "type": "string", "max_length": 80},
                {"name": "display_name", "required": False, "type": "string", "max_length": 165,
                 "notes": "Auto-generated as 'Last Name, First Name' if omitted."},
                {"name": "email_address", "required": True, "type": "string", "max_length": 254},
                {"name": "role", "required": True, "type": "string",
                 "notes": "Must match an existing role name exactly, e.g. 'Engineer'."},
                {"name": "city", "required": True, "type": "string",
                 "notes": "Must match an existing city exactly, e.g. 'London'."},
                {"name": "country", "required": True, "type": "string",
                 "notes": "Must match an existing country exactly, e.g. 'United Kingdom'."},
                {"name": "employment_type", "required": True, "type": "string",
                 "notes": "Must match an existing employment type name exactly, e.g. 'Permanent'."},
                {"name": "team", "required": False, "type": "string",
                 "notes": "Must match an existing team name exactly. Leave blank to leave unassigned."},
                {"name": "start_date", "required": True, "type": "date", "format": "YYYY-MM-DD"},
                {"name": "end_date", "required": False, "type": "date", "format": "YYYY-MM-DD",
                 "notes": "Leave blank if the member is currently active."},
                {"name": "default_holidays", "required": False, "type": "integer",
                 "notes": "Public holiday days per financial year. Defaults to system configuration if omitted."},
                {"name": "is_active", "required": False, "type": "boolean",
                 "allowed_values": ["true", "false"], "default": "true"},
            ],
            "notes": [
                "First row must be the header row.",
                "Boolean fields accept: true / false (case-insensitive).",
                "Date fields must be in YYYY-MM-DD format.",
                "Foreign key fields (role, location, employment_type, team) must match existing records exactly.",
                "Maximum 500 rows per import.",
            ],
        }
        return Response(specs, status=status.HTTP_200_OK)

    # GET /team-members/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing team members.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "first_name", "last_name", "display_name", "email_address",
            "role", "city", "country", "employment_type", "team",
            "start_date", "end_date", "default_holidays", "is_active",
        ])
        writer.writerow([
            "Jane", "Smith", "Smith, Jane", "jane.smith@example.com",
            "Engineer", "London", "United Kingdom", "Permanent", "Team Alpha",
            "2024-01-15", "", "20", "true",
        ])
        writer.writerow([
            "John", "Doe", "", "john.doe@example.com",
            "Lead Engineer", "Manchester", "United Kingdom", "Contractor", "",
            "2023-06-01", "2024-12-31", "20", "true",
        ])
        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="team_members_import_template.csv"'
        return response

    # POST /team-members/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for team members.
        """
        dry_run = request.query_params.get('validate', 'false').lower() == 'true'
        try:
            results = TeamMemberService.bulk_import(request, dry_run=dry_run)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except (DjangoValidationError, DRFValidationError) as e:
            logging.warning("Validation error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Unexpected error in bulk_import: %s", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /team-members/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of team members. Returns JSON. UI handles CSV or PDF formats.
        """
        try:
            qs = TeamMember.objects.all()
            data = TeamMemberExportSerializer(qs, many=True).data
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
