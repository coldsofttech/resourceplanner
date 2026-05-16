from django.shortcuts import render
from django.views.generic import ListView, View

from .models import Configuration


class ConfigurationListView(ListView):
    model = Configuration
    template_name = 'configurations/config_list.html'


class ConfigurationDetailView(View):
    template_name = 'configurations/config_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class ConfigurationUpdateView(View):
    template_name = 'configurations/config_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


# ── Integration views ─────────────────────────────────────────────────────────

class _ModuleListView(View):
    """Base view for module-filtered configuration pages."""
    template_name = 'configurations/module_list.html'
    module = ''
    page_title = ''
    page_subtitle = ''

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {
            'module': self.module,
            'page_title': self.page_title,
            'page_subtitle': self.page_subtitle,
        })


class IntegrationAIListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/integration_ai.html')


class IntegrationEmailListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/integration_email.html')


class IntegrationSSOListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/integration_sso.html')


class IntegrationJiraListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/integration_jira.html')


# ── Security views ────────────────────────────────────────────────────────────

class SecurityListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/security.html')


class SecurityPasswordPolicyListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/security_password.html')
