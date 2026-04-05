import logging

from django.db import DatabaseError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import SprintCapacitySerializer
from .services import SprintCapacityService

logger = logging.getLogger(__name__)


class SprintCapacityViewSet(viewsets.ViewSet):
    """
    Standalone capacity endpoint.

    Supported query params
    ----------------------
    sprint_id   — filter to a single sprint
    fy_id       — filter to all sprints in a FY
    team_id     — filter to members of a team
    member_id   — filter to a single member
    (combinations are AND-ed together)
    """

    # GET /sprint-capacity/
    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 50)), 200)
        except (ValueError, TypeError):
            page, page_size = 1, 50

        try:
            result = SprintCapacityService.list_capacity(
                filters=request.query_params,
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
            logger.exception("DB error in capacity list: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in capacity list: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST /sprint-capacity/rebuild/
    @action(detail=False, methods=['post'], url_path='rebuild')
    def rebuild(self, request):
        """Full capacity rebuild — admin / management use."""
        sprint_id = request.data.get('sprint_id')
        try:
            if sprint_id:
                from apps.sprints.models import Sprint
                sprint = Sprint.objects.get(pk=sprint_id)
                SprintCapacityService.regenerate_for_sprint(sprint)
                return Response(
                    {'message': f'Capacity rebuilt for sprint {sprint.sprint_name}.'},
                    status=status.HTTP_200_OK,
                )
            else:
                result = SprintCapacityService.rebuild_all()
                return Response(
                    {'message': 'Capacity rebuilt successfully.', 'detail': result},
                    status=status.HTTP_200_OK,
                )
        except DatabaseError as e:
            logger.exception("DB error in capacity rebuild: %s", e)
            return Response({'error': 'A database error occurred.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.exception("Unexpected error in capacity rebuild: %s", e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
