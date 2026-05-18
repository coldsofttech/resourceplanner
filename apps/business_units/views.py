from django.shortcuts import render
from django.views.generic import View


class BusinessUnitListView(View):
    template_name = 'business_units/list.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
