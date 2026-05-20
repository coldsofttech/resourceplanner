import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Todo, TodoComment
from .serializers import (
    TodoSerializer, TodoDetailSerializer,
    TodoCommentSerializer, UserMentionSerializer,
)
from .services import TodoService

logger = logging.getLogger(__name__)
User = get_user_model()


class TodoListCreateView(APIView):
    """GET /api/v1/todos/  POST /api/v1/todos/"""

    def get(self, request):
        try:
            page      = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 25

        result = TodoService.list_todos(
            user=request.user,
            scope=request.query_params.get('scope', 'mine'),
            status=request.query_params.get('status') or None,
            priority=request.query_params.get('priority') or None,
            due_filter=request.query_params.get('due_filter') or None,
            search=request.query_params.get('search') or None,
            page=page,
            page_size=page_size,
        )
        return Response({
            'results': TodoSerializer(result['results'], many=True).data,
            'pagination': {
                'total_count':  result['total_count'],
                'total_pages':  result['total_pages'],
                'current_page': result['current_page'],
                'has_next':     result['has_next'],
                'has_previous': result['has_previous'],
            },
        })

    def post(self, request):
        data = request.data

        if not data.get('title', '').strip():
            return Response({'title': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        assigned_user = None
        if data.get('assigned_to'):
            try:
                assigned_user = User.objects.get(pk=data['assigned_to'], is_active=True)
            except User.DoesNotExist:
                return Response({'assigned_to': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)

        create_data = {
            'title':              data['title'].strip(),
            'description':        data.get('description', ''),
            'priority':           data.get('priority', Todo.PRIORITY_MEDIUM),
            'due_date':           data.get('due_date') or None,
            'reminder_at':        data.get('reminder_at') or None,
            'assigned_to':        assigned_user,
            'is_recurring':       bool(data.get('is_recurring', False)),
            'recurrence_rule':    data.get('recurrence_rule', ''),
            'recurrence_interval': int(data.get('recurrence_interval', 1)),
            'recurrence_end_date': data.get('recurrence_end_date') or None,
        }

        todo = TodoService.create(request.user, create_data)
        return Response(TodoDetailSerializer(todo).data, status=status.HTTP_201_CREATED)


class TodoDetailView(APIView):
    """GET / PATCH / DELETE /api/v1/todos/<pk>/"""

    def _get_todo(self, pk, user):
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return None
        return todo

    def get(self, request, pk):
        todo = self._get_todo(pk, request.user)
        if not todo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TodoDetailSerializer(todo).data)

    def patch(self, request, pk):
        todo = self._get_todo(pk, request.user)
        if not todo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = dict(request.data)

        assigned_user = None
        if 'assigned_to' in data:
            raw = data['assigned_to']
            if raw:
                try:
                    assigned_user = User.objects.get(pk=raw, is_active=True)
                except User.DoesNotExist:
                    return Response({'assigned_to': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)
            data['assigned_to'] = assigned_user

        todo = TodoService.update(todo, data, request.user)
        return Response(TodoDetailSerializer(todo).data)

    def delete(self, request, pk):
        todo = self._get_todo(pk, request.user)
        if not todo:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        todo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TodoCompleteView(APIView):
    """POST /api/v1/todos/<pk>/complete/"""

    def post(self, request, pk):
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if todo.status == Todo.STATUS_DONE:
            return Response({'detail': 'Already completed.'}, status=status.HTTP_400_BAD_REQUEST)

        todo = TodoService.complete(todo, request.user)
        return Response(TodoDetailSerializer(todo).data)


class TodoReopenView(APIView):
    """POST /api/v1/todos/<pk>/reopen/"""

    def post(self, request, pk):
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if todo.status != Todo.STATUS_DONE:
            return Response({'detail': 'Todo is not completed.'}, status=status.HTTP_400_BAD_REQUEST)

        todo = TodoService.reopen(todo)
        return Response(TodoDetailSerializer(todo).data)


class TodoCommentListCreateView(APIView):
    """GET /api/v1/todos/<pk>/comments/   POST /api/v1/todos/<pk>/comments/"""

    def get(self, request, pk):
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        comments = todo.comments.select_related('created_by').all()
        return Response(TodoCommentSerializer(comments, many=True).data)

    def post(self, request, pk):
        try:
            todo = Todo.objects.get(pk=pk)
        except Todo.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({'content': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        comment = TodoService.add_comment(todo, request.user, content)
        return Response(TodoCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class TodoCommentDetailView(APIView):
    """PATCH / DELETE /api/v1/todos/<pk>/comments/<cpk>/"""

    def _get_comment(self, todo_pk, cpk):
        try:
            return TodoComment.objects.get(pk=cpk, todo_id=todo_pk)
        except TodoComment.DoesNotExist:
            return None

    def patch(self, request, pk, cpk):
        comment = self._get_comment(pk, cpk)
        if not comment:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({'content': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        comment = TodoService.update_comment(comment, content, request.user)
        return Response(TodoCommentSerializer(comment).data)

    def delete(self, request, pk, cpk):
        comment = self._get_comment(pk, cpk)
        if not comment:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        TodoService.delete_comment(comment, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TodoMentionUsersView(APIView):
    """GET /api/v1/todos/mention-users/?q=alice  — autocomplete for @mentions."""

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 1:
            return Response([])

        users = User.objects.filter(
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q),
            is_active=True,
        ).exclude(pk=request.user.pk)[:10]

        return Response(UserMentionSerializer(users, many=True).data)
