from django.contrib import messages
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View

from .forms import SkillForm
from .models import Skill
from .services import SkillService


class SkillListView(ListView):
    """
    List view for skills.
    """
    model = Skill
    template_name = 'skills/skill_list.html'
    context_object_name = 'skills'

    def get_queryset(self):
        return SkillService.list_skills()

    def get_context_data(
            self, *, object_list=..., **kwargs
    ):
        """
        total_skills: count of all skills
        active_skills: count of active skills
        inactive_skills: count of inactive skills
        unassigned_skills: count of unassigned skills
        """
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['total_skills'] = qs.count()
        ctx['active_skills'] = qs.filter(is_active=True).count()
        ctx['inactive_skills'] = qs.filter(is_active=False).count()

        # unassigned skills is yet to be added

        return ctx


class SkillCreateView(CreateView):
    """
    Create view for skills.
    """
    model = Skill
    form_class = SkillForm
    template_name = 'skills/skill_form.html'
    success_url = reverse_lazy('skills:list')

    def form_valid(self, form):
        try:
            skill = SkillService.create_skill(form.cleaned_data)
            messages.success(self.request, f"Skill '{skill.skill}' created successfully.")
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            form.add_error('skill', e.message if hasattr(e, 'message') else str(e))
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class SkillDetailView(DetailView):
    """
    Detail view for skills.
    """
    model = Skill
    form_class = SkillForm
    template_name = 'skills/skill_detail.html'
    context_object_name = 'skill'

    def get_object(self, queryset=...):
        return SkillService.get_skill(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Return list of associated team members
        # Return additional context: member_count, active_member_count, inactive_member_count

        return ctx


class SkillUpdateView(UpdateView):
    """
    Update view for skills.
    """
    model = Skill
    form_class = SkillForm
    template_name = 'skills/skill_form.html'
    success_url = reverse_lazy('skills:list')

    def get_object(self, queryset=...):
        try:
            return SkillService.get_skill(self.kwargs['pk'])
        except Skill.DoesNotExist:
            raise Http404(f"Skill {self.kwargs['pk']} does not exist.")

    def form_valid(self, form):
        try:
            updated_skill = SkillService.update_skill(self.object.pk, form.cleaned_data)
            messages.success(self.request, f"Skill '{updated_skill.skill}' updated successfully.")
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            form.add_error(None, e.message if hasattr(e, 'message') else str(e))
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class SkillDeleteView(DeleteView):
    """
    Delete view for skills.
    """
    model = Skill
    success_url = reverse_lazy('skills:list')

    def get_object(self, queryset=...):
        try:
            return SkillService.get_skill(self.kwargs['pk'])
        except Skill.DoesNotExist:
            raise Http404(f"Skill {self.kwargs['pk']} does not exist.")

    def post(self, request, *args, **kwargs):
        is_ajax = request.headers.get('Content-Type') == 'application/json'
        try:
            skill = self.get_object()
            skill_code = skill.skill
            success_msg = f"Skill '{skill_code}' deleted successfully."
            SkillService.delete_skill(skill.pk)
            if is_ajax:
                return JsonResponse({"detail": success_msg, }, status=200)
            messages.success(request, success_msg)
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            error_msg = e.message if hasattr(e, 'message') else str(e)
            if is_ajax:
                return JsonResponse({"detail": error_msg, }, status=400)
            messages.error(request, error_msg)
            return HttpResponseRedirect(self.success_url)

    # Block GET — confirmation is handled by the modal, not a separate page
    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(self.success_url)


class SkillImportView(View):
    """
    Import view for skills.
    """
    template_name = 'skills/skill_import.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        try:
            results = SkillService.bulk_import(request)
            return JsonResponse(results, status=207)
        except Exception as e:
            return JsonResponse(
                {
                    "error": e.messages if hasattr(e, 'messages') else str(e),
                }, status=400
            )
