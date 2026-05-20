from django.urls import path

from .api_views import (
    TodoListCreateView,
    TodoDetailView,
    TodoCompleteView,
    TodoReopenView,
    TodoCommentListCreateView,
    TodoCommentDetailView,
    TodoMentionUsersView,
)

urlpatterns = [
    path('todos/',                                    TodoListCreateView.as_view(),        name='todo-list'),
    path('todos/mention-users/',                      TodoMentionUsersView.as_view(),      name='todo-mention-users'),
    path('todos/<int:pk>/',                           TodoDetailView.as_view(),            name='todo-detail'),
    path('todos/<int:pk>/complete/',                  TodoCompleteView.as_view(),          name='todo-complete'),
    path('todos/<int:pk>/reopen/',                    TodoReopenView.as_view(),            name='todo-reopen'),
    path('todos/<int:pk>/comments/',                  TodoCommentListCreateView.as_view(), name='todo-comments'),
    path('todos/<int:pk>/comments/<int:cpk>/',        TodoCommentDetailView.as_view(),     name='todo-comment-detail'),
]
