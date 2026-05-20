from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Todo


@login_required
def todos_list(request):
    return render(request, 'todos/list.html')


@login_required
def todo_detail(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    return render(request, 'todos/detail.html', {'todo_pk': pk, 'todo': todo})
