from django.contrib import messages
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View

from .forms import DeliveryTeamForm
from .models import DeliveryTeam
from .services import DeliveryTeamService


class DeliveryTeamListView(ListView):
    """
    List view for delivery teams.
    """
    model = DeliveryTeam
    template_name = 'delivery_teams/delivery_team_list.html'
    context_object_name = 'delivery_teams'

    def get_queryset(self):
        return DeliveryTeamService.list_teams()

    def get_context_data(
            self, *, object_list=..., **kwargs
    ):
        """
        total_teams: count of all delivery teams
        active_teams: count of all active delivery teams
        total_members: count of all delivery team members
        unassigned_members: count of unassigned delivery team members
        """
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx['total_teams'] = qs.count()
        ctx['active_teams'] = qs.filter(is_active=True).count()

        # team members functionality is yet to be added

        return ctx


class DeliveryTeamCreateView(CreateView):
    """
    Create view for delivery teams.
    """
    model = DeliveryTeam
    form_class = DeliveryTeamForm
    template_name = 'delivery_teams/delivery_team_form.html'
    success_url = reverse_lazy('delivery_teams:list')

    def form_valid(self, form):
        try:
            team = DeliveryTeamService.create_team(form.cleaned_data)
            messages.success(self.request, f"Team '{team.name}' created successfully.")
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            form.add_error('name', e.message if hasattr(e, 'message') else str(e))
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DeliveryTeamDetailView(DetailView):
    """
    Detail view for delivery teams.
    """
    model = DeliveryTeam
    form_class = DeliveryTeamForm
    template_name = 'delivery_teams/delivery_team_detail.html'
    context_object_name = 'delivery_team'

    def get_object(self, queryset=...):
        return DeliveryTeamService.get_team(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Return list of associated team members
        # Return list of associated projects (both as assigned teams & collaborators)
        # Return list of planned leaves from team members

        return ctx


class DeliveryTeamUpdateView(UpdateView):
    """
    Update view for delivery teams.
    """
    model = DeliveryTeam
    form_class = DeliveryTeamForm
    template_name = 'delivery_teams/delivery_team_form.html'
    success_url = reverse_lazy('delivery_teams:list')

    def get_object(self, queryset=...):
        try:
            return DeliveryTeamService.get_team(self.kwargs['pk'])
        except DeliveryTeam.DoesNotExist:
            raise Http404(f"Team {self.kwargs['pk']} does not exist.")

    def form_valid(self, form):
        try:
            updated_team = DeliveryTeamService.update_team(self.object.pk, form.cleaned_data)
            messages.success(self.request, f"Team '{updated_team.name}' updated successfully.")
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            form.add_error(None, e.message if hasattr(e, 'message') else str(e))
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DeliveryTeamDeleteView(DeleteView):
    """
    Delete view for delivery teams.
    """
    model = DeliveryTeam
    success_url = reverse_lazy('delivery_teams:list')

    def get_object(self, queryset=...):
        try:
            return DeliveryTeamService.get_team(self.kwargs['pk'])
        except DeliveryTeam.DoesNotExist:
            raise Http404(f"Team {self.kwargs['pk']} does not exist.")

    def post(self, request, *args, **kwargs):
        is_ajax = request.headers.get('Content-Type') == 'application/json'
        try:
            team = self.get_object()
            team_name = team.name
            success_msg = f"Team '{team_name}' deleted successfully."
            DeliveryTeamService.delete_team(team.pk)
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


class DeliveryTeamImportView(View):
    """
    Import view for delivery teams.
    """
    template_name = 'delivery_teams/delivery_team_import.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        try:
            results = DeliveryTeamService.bulk_import(request)
            return JsonResponse(results, status=207)
        except Exception as e:
            return JsonResponse(
                {
                    "error": e.messages if hasattr(e, 'messages') else str(e),
                }, status=400
            )
