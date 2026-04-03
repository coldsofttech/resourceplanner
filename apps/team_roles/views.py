from django.shortcuts import render
from django.views.generic import ListView, View

from .models import TeamRole


class TeamRoleListView(ListView):
    """
    List view for team roles.
    """
    model = TeamRole
    template_name = 'team_roles/role_list.html'


class TeamRoleCreateView(View):
    """
    Create view for team roles.
    """
    template_name = 'team_roles/role_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class TeamRoleDetailView(View):
    """
    Detail view for team roles.
    """
    template_name = 'team_roles/role_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class TeamRoleUpdateView(View):
    """
    Update view for team roles.
    """
    template_name = 'team_roles/role_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
