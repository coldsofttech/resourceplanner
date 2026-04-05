from django.shortcuts import render
from django.views.generic import View, ListView

from .models import Sprint


class SprintListView(ListView):
    model = Sprint
    template_name = 'sprints/sprint_list.html'


class SprintCreateView(View):
    template_name = 'sprints/sprint_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class SprintDetailView(View):
    template_name = 'sprints/sprint_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class SprintUpdateView(View):
    template_name = 'sprints/sprint_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
