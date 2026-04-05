from django.shortcuts import render
from django.views.generic import ListView, View

from .models import ProjectType


class ProjectTypeListView(ListView):
    model = ProjectType
    template_name = 'project_types/type_list.html'


class ProjectTypeCreateView(View):
    template_name = 'project_types/type_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class ProjectTypeDetailView(View):
    template_name = 'project_types/type_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class ProjectTypeUpdateView(View):
    template_name = 'project_types/type_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
