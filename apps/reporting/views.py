from django.views.generic import TemplateView

_SLUG_TEMPLATES = {
    'sprint-forecast-actuals': 'reporting/sprint_fa_report.html',
    'kpi-estimate-accuracy':   'reporting/kpi_report.html',
    'monthly-finance':         'reporting/monthly_finance_report.html',
}

_CONFIGURE_SLUG_TEMPLATES = {
    'kpi-estimate-accuracy': 'reporting/kpi_configure.html',
}


class ReportingIndexView(TemplateView):
    template_name = "reporting/index.html"


class StandardReportView(TemplateView):
    template_name = "reporting/standard_report.html"

    def get_template_names(self):
        slug = self.kwargs.get('slug', '')
        return [_SLUG_TEMPLATES.get(slug, self.template_name)]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.kwargs["slug"]
        return ctx


class StandardReportConfigureView(TemplateView):
    template_name = "reporting/configure.html"

    def get_template_names(self):
        slug = self.kwargs.get('slug', '')
        return [_CONFIGURE_SLUG_TEMPLATES.get(slug, self.template_name)]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.kwargs["slug"]
        return ctx
