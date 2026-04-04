from django.shortcuts import render
from django.views.generic import ListView, View

from .models import PublicHoliday


class PublicHolidayListView(ListView):
    """
    Renders the holiday list shell. Table data is populated by JS via the API.
    """
    model = PublicHoliday
    template_name = 'public_holidays/holiday_list.html'


class PublicHolidayCreateView(View):
    """
    Renders the create-holiday form shell. JS posts to the API.
    """
    template_name = 'public_holidays/holiday_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class PublicHolidayDetailView(View):
    """
    Renders the holiday detail shell. JS fetches data via the API.
    """
    template_name = 'public_holidays/holiday_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class PublicHolidayUpdateView(View):
    """
    Renders the edit-holiday form shell. JS fetches existing data and posts updates to the API.
    """
    template_name = 'public_holidays/holiday_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
