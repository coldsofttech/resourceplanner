from django.shortcuts import render
from django.views.generic import View


class ProjectSubStatusView(View):
    template_name = 'project_sub_statuses/status_list.html'

    def get(self, request):
        return render(request, self.template_name)
