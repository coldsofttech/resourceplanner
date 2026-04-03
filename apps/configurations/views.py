from django.shortcuts import render
from django.views.generic import ListView, View

from .models import Configuration


class ConfigurationListView(ListView):
    """
    List view for configurations.
    """
    model = Configuration
    template_name = 'configurations/config_list.html'


class ConfigurationDetailView(View):
    """
    Detail view for configurations.
    """
    template_name = 'configurations/config_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class ConfigurationUpdateView(View):
    """
    Update view for configurations.
    """
    template_name = 'configurations/config_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
