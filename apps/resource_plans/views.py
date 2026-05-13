from django.shortcuts import render
from django.views.generic import View, TemplateView


class ResourcePlanListView(View):
    template_name = "resource_plans/plan_list.html"

    def get(self, request):
        return render(request, self.template_name)


class ResourcePlanDetailView(View):
    template_name = "resource_plans/plan_detail.html"

    def get(self, request, pk):
        return render(request, self.template_name, {"plan_pk": pk})


class VersionConfigureView(View):
    template_name = "resource_plans/version_configure.html"

    def get(self, request, plan_pk, version_pk):
        return render(request, self.template_name, {
            "plan_pk": plan_pk,
            "version_pk": version_pk,
        })


class AllocationGridView(View):
    template_name = "resource_plans/allocation_grid.html"

    def get(self, request, plan_pk, version_pk):
        return render(request, self.template_name, {
            "plan_pk": plan_pk,
            "version_pk": version_pk,
        })


class PlaceholderLeavesView(View):
    template_name = "resource_plans/placeholder_leaves.html"

    def get(self, request, plan_pk, version_pk):
        return render(request, self.template_name, {
            "plan_pk": plan_pk,
            "version_pk": version_pk,
        })


class ConflictsView(TemplateView):
    template_name = "resource_plans/conflicts.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['plan_pk'] = self.kwargs['plan_pk']
        ctx['version_pk'] = self.kwargs['version_pk']
        return ctx


class UtilisationView(View):
    template_name = "resource_plans/utilisation.html"

    def get(self, request, plan_pk, version_pk):
        return render(request, self.template_name, {
            "plan_pk": plan_pk,
            "version_pk": version_pk,
        })


class SnapshotsView(View):
    template_name = "resource_plans/snapshots.html"

    def get(self, request, plan_pk, version_pk):
        return render(request, self.template_name, {
            "plan_pk": plan_pk,
            "version_pk": version_pk,
        })
