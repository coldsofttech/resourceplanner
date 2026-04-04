from django.shortcuts import render
from django.views.generic import ListView, View

from .models import TeamMember


class TeamMemberListView(ListView):
    """
    List view for team members.
    """
    model = TeamMember
    template_name = 'team_members/member_list.html'


class TeamMemberCreateView(View):
    """
    Create view for team members.
    """
    template_name = 'team_members/member_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class TeamMemberDetailView(View):
    """
    Detail view for team members.
    """
    template_name = 'team_members/member_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class TeamMemberUpdateView(View):
    """
    Update view for team members.
    """
    template_name = 'team_members/member_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
