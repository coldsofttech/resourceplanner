from django.urls import path

from . import views

urlpatterns = [
    path('',          views.todos_list,  name='todos-list'),
    path('<int:pk>/', views.todo_detail, name='todo-detail'),
]
