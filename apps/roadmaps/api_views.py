import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer

from .models import Roadmap, RoadmapItem, RoadmapMilestone, RoadmapTask
from .serializers import (
    RoadmapListSerializer,
    RoadmapMilestoneSerializer,
    RoadmapItemSerializer,
    RoadmapSerializer,
    RoadmapTaskSerializer,
)

logger = logging.getLogger(__name__)


class RoadmapViewSet(viewsets.ViewSet):

    def list(self, request):
        qs = Roadmap.objects.all()
        serializer = RoadmapListSerializer(qs, many=True)
        return Response({'results': serializer.data})

    def create(self, request):
        serializer = RoadmapListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roadmap = serializer.save(created_by=request.user)
        return Response(RoadmapListSerializer(roadmap).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            roadmap = Roadmap.objects.prefetch_related(
                'items__milestones',
                'items__tasks__assignee',
                'items__tasks__start_sprint',
                'items__tasks__end_sprint',
                'items__start_sprint',
                'items__end_sprint',
                'items__project',
                'items__programme',
                'items__assigned_team',
            ).get(pk=pk)
        except Roadmap.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RoadmapSerializer(roadmap).data)

    def update(self, request, pk=None):
        try:
            roadmap = Roadmap.objects.get(pk=pk)
        except Roadmap.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RoadmapListSerializer(roadmap, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk)

    def destroy(self, request, pk=None):
        try:
            roadmap = Roadmap.objects.get(pk=pk)
        except Roadmap.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        roadmap.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='import-projects')
    def import_projects(self, request):
        """Return projects available to import into a roadmap."""
        projects = Project.objects.filter(is_active=True).select_related(
            'programme', 'project_type', 'assigned_team',
        ).order_by('name')
        serializer = ProjectSerializer(projects, many=True)
        return Response({'results': serializer.data})


class RoadmapItemViewSet(viewsets.ViewSet):

    def list(self, request):
        roadmap_id = request.query_params.get('roadmap')
        qs = RoadmapItem.objects.select_related(
            'project', 'programme', 'assigned_team', 'start_sprint', 'end_sprint',
        ).prefetch_related('milestones', 'tasks__assignee', 'tasks__start_sprint', 'tasks__end_sprint')
        if roadmap_id:
            qs = qs.filter(roadmap_id=roadmap_id)
        serializer = RoadmapItemSerializer(qs, many=True)
        return Response({'results': serializer.data})

    def create(self, request):
        serializer = RoadmapItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(RoadmapItemSerializer(item).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            item = RoadmapItem.objects.prefetch_related('milestones').get(pk=pk)
        except RoadmapItem.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RoadmapItemSerializer(item).data)

    def update(self, request, pk=None):
        try:
            item = RoadmapItem.objects.get(pk=pk)
        except RoadmapItem.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RoadmapItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RoadmapItemSerializer(item).data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk)

    def destroy(self, request, pk=None):
        try:
            item = RoadmapItem.objects.get(pk=pk)
        except RoadmapItem.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """Bulk update display_order. Expects [{id, display_order}, ...]"""
        items = request.data if isinstance(request.data, list) else []
        for entry in items:
            RoadmapItem.objects.filter(pk=entry['id']).update(display_order=entry['display_order'])
        return Response({'status': 'ok'})


class RoadmapMilestoneViewSet(viewsets.ViewSet):

    def list(self, request):
        item_id = request.query_params.get('roadmap_item')
        qs = RoadmapMilestone.objects.select_related('sprint')
        if item_id:
            qs = qs.filter(roadmap_item_id=item_id)
        serializer = RoadmapMilestoneSerializer(qs, many=True)
        return Response({'results': serializer.data})

    def create(self, request):
        serializer = RoadmapMilestoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        milestone = serializer.save()
        return Response(RoadmapMilestoneSerializer(milestone).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        try:
            milestone = RoadmapMilestone.objects.get(pk=pk)
        except RoadmapMilestone.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RoadmapMilestoneSerializer(milestone, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RoadmapMilestoneSerializer(milestone).data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk)

    def destroy(self, request, pk=None):
        try:
            milestone = RoadmapMilestone.objects.get(pk=pk)
        except RoadmapMilestone.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        milestone.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoadmapTaskViewSet(viewsets.ViewSet):

    def list(self, request):
        item_id = request.query_params.get('roadmap_item')
        qs = RoadmapTask.objects.select_related('assignee', 'start_sprint', 'end_sprint')
        if item_id:
            qs = qs.filter(roadmap_item_id=item_id)
        serializer = RoadmapTaskSerializer(qs, many=True)
        return Response({'results': serializer.data})

    def create(self, request):
        serializer = RoadmapTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response(RoadmapTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        try:
            task = RoadmapTask.objects.get(pk=pk)
        except RoadmapTask.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RoadmapTaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(RoadmapTaskSerializer(task).data)

    def partial_update(self, request, pk=None):
        return self.update(request, pk)

    def destroy(self, request, pk=None):
        try:
            task = RoadmapTask.objects.get(pk=pk)
        except RoadmapTask.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
