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


class IntegrationAIListView(_ModuleListView):
    module = 'integration_ai'
    page_title = 'AI Integration'
    page_subtitle = 'Configure AI provider and model settings.'


class IntegrationEmailListView(_ModuleListView):
    module = 'integration_email'
    page_title = 'Email Integration'
    page_subtitle = 'Configure outbound email (SMTP) settings.'


class IntegrationSSOListView(_ModuleListView):
    module = 'integration_sso'
    page_title = 'SSO Integration'
    page_subtitle = 'Configure Single Sign-On via OAuth2 or SAML 2.0.'


class IntegrationJiraListView(_ModuleListView):
    module = 'integration_jira'
    page_title = 'Jira Integration'
    page_subtitle = 'Configure Jira project management integration.'


# ── Security views ────────────────────────────────────────────────────────────

class SecurityListView(_ModuleListView):
    module = 'security'
    page_title = 'Security'
    page_subtitle = 'Authentication mode, session, and access control settings.'


class SecurityPasswordPolicyListView(_ModuleListView):
    module = 'security_password'
    page_title = 'Password Policy'
    page_subtitle = 'Configure password strength requirements and rotation rules.'
