from django.shortcuts import render
from django.views.generic import View


class ProjectListView(View):
    template_name = "projects/project_list.html"

    def get(self, request):
        return render(request, self.template_name)


class ProjectDetailView(View):
    template_name = "projects/project_detail.html"

    def get(self, request, pk):
        return render(request, self.template_name, {"project_pk": pk})
