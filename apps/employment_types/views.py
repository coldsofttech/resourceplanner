from django.shortcuts import render
from django.views.generic import ListView, View

from .models import EmploymentType


class EmploymentTypeListView(ListView):
    """
    List view for employment types.
    """
    model = EmploymentType
    template_name = 'employment_types/type_list.html'


class EmploymentTypeCreateView(View):
    """
    Create view for employment types.
    """
    template_name = 'employment_types/type_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class EmploymentTypeDetailView(View):
    """
    Detail view for employment types.
    """
    template_name = 'employment_types/type_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class EmploymentTypeUpdateView(View):
    """
    Update view for employment types.
    """
    template_name = 'employment_types/type_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
