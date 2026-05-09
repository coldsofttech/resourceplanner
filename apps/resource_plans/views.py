from django.shortcuts import render
from django.views.generic import View


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
