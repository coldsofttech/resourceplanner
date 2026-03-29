import csv
import io
import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import SkillSerializer, SkillExportSerializer
from .services import SkillService

logger = logging.getLogger(__name__)


class SkillViewSet(viewsets.ViewSet):
    # GET /skills/
    def list(self, request):
        """
        List all skills.
        """
        try:
            skills = SkillService.list_skills(filters=request.query_params)
            serializer = SkillSerializer(skills, many=True)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except DatabaseError as e:
            logging.exception("Database error in list_skills: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list_skills: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /skills/<id>/
    def retrieve(self, request, pk=None):
        """
        Retrieve a single skill by specified skill id.
        """
        try:
            skill = SkillService.get_skill(pk)
            serializer = SkillSerializer(skill)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in get_skill: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in get_skill: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in get_skill: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # POST /skills/
    def create(self, request):
        """
        Create a new skill.
        """
        try:
            serializer = SkillSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            skill = SkillService.create_skill(serializer.validated_data)
            return Response(
                SkillSerializer(skill).data,
                status=status.HTTP_201_CREATED,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in create_skill: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in create_skill: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in create_skill: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _perform_update(self, request, pk, partial: bool):
        """
        Update a skill by specified skill id.
        """
        try:
            serializer = SkillSerializer(data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            skill = SkillService.update_skill(pk, serializer.validated_data)
            return Response(
                SkillSerializer(skill).data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in update_skill: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in update_skill: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in update_skill: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # PUT /skills/<id>/
    def update(self, request, pk=None):
        """
        Update a skill by specified skill id.
        """
        return self._perform_update(request, pk, partial=False)

    # PATCH /skills/<id>/
    def partial_update(self, request, pk=None):
        """
        Update a skill by specified skill id for the specified fields.
        """
        return self._perform_update(request, pk, partial=True)

    # DELETE /skills/<id>/
    def destroy(self, request, pk=None):
        """
        Delete a skill by specified skill id.
        """
        try:
            SkillService.delete_skill(pk)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ValidationError, ValueError) as e:
            logging.warning("Validation error in delete_skill: %s", e)
            return Response(
                {
                    "error": "Invalid parameters/values.",
                    "details": e.message_dict if hasattr(e, 'message_dict') else e.messages,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError as e:
            logging.exception("Database error in delete_skill: %s", e)
            return Response(
                {
                    "error": "A database error occurred. Please try again later.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in delete_skill: %s", e)
            return Response(
                {
                    "error": "An unexpected error occurred. Please try again later.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # GET /skills/import/specifications/
    @action(detail=False, methods=['get'], url_path='import/specifications')
    def import_specifications(self, request):
        """
        Import specifications for skills.
        """
        specs = {
            "fields": [
                {"name": "skill", "required": True, "type": "string", "max_length": 20},
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

    # GET /skills/import/sample/
    @action(detail=False, methods=['get'], url_path='import/sample')
    def import_sample(self, request):
        """
        A sample template for importing skills.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["skill", "description", "is_active"])  # header
        writer.writerow(["AWSENGINEER", "Example description", "true"])  # sample row

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="skills_import_template.csv"'
        return response

    # POST /skills/import/
    @action(detail=False, methods=['post'], url_path='import')
    def bulk_import(self, request):
        """
        Bulk import for skills.
        """
        try:
            results = SkillService.bulk_import(request)
            return Response(results, status=status.HTTP_207_MULTI_STATUS)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET /skills/export/
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """
        Export of skills. Returns JSON. UI to handle CSV or PDF formats.
        """
        try:
            skills = SkillService.list_skills(filters=request.query_params)
            data = SkillExportSerializer(skills, many=True).data
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
