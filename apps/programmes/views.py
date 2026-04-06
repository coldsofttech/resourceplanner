from django.shortcuts import render
from django.views.generic import View


class ProgrammeListView(View):
    template_name = "programmes/programme_list.html"

    def get(self, request):
        return render(request, self.template_name)
