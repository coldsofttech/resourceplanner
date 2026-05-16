from django.views.generic import TemplateView


class ReportingIndexView(TemplateView):
    template_name = "reporting/index.html"


class StandardReportView(TemplateView):
    template_name = "reporting/standard_report.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.kwargs["slug"]
        return ctx


class StandardReportConfigureView(TemplateView):
    template_name = "reporting/configure.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["slug"] = self.kwargs["slug"]
        return ctx
