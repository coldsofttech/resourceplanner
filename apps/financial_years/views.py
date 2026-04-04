from django.shortcuts import render
from django.views.generic import View, ListView

from .models import FinancialYear


class FinancialYearListView(ListView):
    model = FinancialYear
    template_name = 'financial_years/fy_list.html'


class FinancialYearCreateView(View):
    template_name = 'financial_years/fy_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class FinancialYearDetailView(View):
    template_name = 'financial_years/fy_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class FinancialYearUpdateView(View):
    template_name = 'financial_years/fy_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
