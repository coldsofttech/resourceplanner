import logging

from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.response import Response


from .serializers import TagSerializer
from .services import TagService

logger = logging.getLogger(__name__)


class TagViewSet(viewsets.ViewSet):
    # GET /tags/
    def list(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        try:
            result = TagService.list_tags(
                filters=request.query_params,
                page=page,
                page_size=page_size,
            )
            serializer = TagSerializer(result["results"], many=True)
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
            logger.exception("DatabaseError in list: %s", e)
            return Response(
                {"error": "A database error occurred. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in list: %s", e)
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
