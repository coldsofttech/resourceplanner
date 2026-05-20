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
        base = request.build_absolute_uri('/').rstrip('/')
        return render(request, 'configurations/integration_sso.html', {
            'sp_base_url':        base,
            'oauth2_redirect_uri': f'{base}/sso/oauth/callback/',
            'saml_entity_id':     base,
            'saml_acs_url':       f'{base}/saml/acs/',
            'saml_metadata_url':  f'{base}/saml2/metadata/',
        })


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


# ── Project Approval view ─────────────────────────────────────────────────────

class ProjectApprovalListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/project_approval.html')


# ── Recharge Contacts view ────────────────────────────────────────────────────

class RechargeContactsListView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/recharge_contacts.html')


# ── Database configuration view ───────────────────────────────────────────────

class DatabaseConfigView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/database.html')


# ── Board Cards configuration view ───────────────────────────────────────────

class BoardCardsConfigView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'configurations/board_cards.html')
