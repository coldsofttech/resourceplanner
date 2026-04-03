from django.shortcuts import render
from django.views.generic import ListView, View

from .models import Skill


class SkillListView(ListView):
    """
    List view for skills.
    """
    model = Skill
    template_name = 'skills/skill_list.html'


class SkillCreateView(View):
    """
    Create view for skills.
    """
    template_name = 'skills/skill_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class SkillDetailView(View):
    """
    Detail view for skills.
    """
    template_name = 'skills/skill_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class SkillUpdateView(View):
    """
    Update view for skills.
    """
    template_name = 'skills/skill_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
