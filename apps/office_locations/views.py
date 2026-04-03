from django.shortcuts import render
from django.views.generic import ListView, View

from .models import OfficeLocation


class OfficeLocationListView(ListView):
    """
    List view for office locations.
    """
    model = OfficeLocation
    template_name = 'office_locations/location_list.html'


class OfficeLocationCreateView(View):
    """
    Create view for office locations.
    """
    template_name = 'office_locations/location_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class OfficeLocationDetailView(View):
    """
    Detail view for office locations.
    """
    template_name = 'office_locations/location_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class OfficeLocationUpdateView(View):
    """
    Update view for office locations.
    """
    template_name = 'office_locations/location_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
