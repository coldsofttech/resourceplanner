from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

_SLUG_TEMPLATES = {
    'sprint-forecast-actuals': 'reporting/sprint_fa_report.html',
    'kpi-estimate-accuracy':   'reporting/kpi_report.html',
    'monthly-finance':         'reporting/monthly_finance_report.html',
}

# Slugs that have dedicated pages — redirect rather than rendering a generic template
_SLUG_REDIRECTS = {
    'weekly-wins': '/wins/report/',
    'monthly-wins': '/wins/monthly/',
}

_CONFIGURE_SLUG_TEMPLATES = {
    'kpi-estimate-accuracy': 'reporting/kpi_configure.html',
}


class ReportingIndexView(TemplateView):
    template_name = "reporting/index.html"


class StandardReportView(TemplateView):
    template_name = "reporting/standard_report.html"

    def get(self, request, *args, **kwargs):
        slug = self.kwargs.get('slug', '')
        if slug in _SLUG_REDIRECTS:
            return redirect(_SLUG_REDIRECTS[slug])
        return super().get(request, *args, **kwargs)

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


class CustomReportListView(TemplateView):
    template_name = "reporting/custom_report_list.html"


class CustomReportEditorView(TemplateView):
    template_name = "reporting/custom_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        ctx['report_pk'] = pk or 'null'
        return ctx
