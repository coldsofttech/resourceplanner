from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from apps.sprints.models import Sprint
from .models import ForecastImport


class SprintForecastPageView(View):
    template_name = 'sprint_forecast/forecast.html'

    def get(self, request, pk, *args, **kwargs):
        sprint = get_object_or_404(Sprint, pk=pk)
        return render(request, self.template_name, {'sprint': sprint})


class SprintActualsPageView(View):
    template_name = 'sprint_forecast/actuals.html'

    def get(self, request, pk, *args, **kwargs):
        sprint = get_object_or_404(Sprint, pk=pk)
        return render(request, self.template_name, {'sprint': sprint})


class ForecastImportDetailPageView(View):
    template_name = 'sprint_forecast/import_detail.html'

    def get(self, request, pk, import_pk, *args, **kwargs):
        sprint = get_object_or_404(Sprint, pk=pk)
        fi = get_object_or_404(ForecastImport, pk=import_pk, sprint=sprint)
        return render(request, self.template_name, {'sprint': sprint, 'forecast_import': fi})


class RechargesPageView(View):
    template_name = 'sprint_forecast/recharges.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class FinanceTypesPageView(View):
    template_name = 'sprint_forecast/finance_types.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
