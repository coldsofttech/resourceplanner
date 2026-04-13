from django.shortcuts import render
from django.views.generic import ListView, View

from .models import DeliveryTeam


class DeliveryTeamListView(ListView):
    """
    List view for delivery teams.
    """

    model = DeliveryTeam
    template_name = "delivery_teams/delivery_team_list.html"


class DeliveryTeamCreateView(View):
    """
    Create view for delivery teams.
    """

    template_name = "delivery_teams/delivery_team_form.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class DeliveryTeamDetailView(View):
    """
    Detail view for delivery teams.
    """

    template_name = "delivery_teams/delivery_team_detail.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class DeliveryTeamUpdateView(View):
    """
    Update view for delivery teams.
    """

    template_name = "delivery_teams/delivery_team_form.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
