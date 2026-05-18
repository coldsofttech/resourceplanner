from django.http import Http404
from django.shortcuts import render
from django.views import View

from .models import SCENARIO_CHOICES, TABLE_SCENARIOS


class EmailTemplateListView(View):
    def get(self, request):
        return render(request, 'email_templates/list.html')


class EmailTemplateEditorView(View):
    def get(self, request, scenario):
        valid = dict(SCENARIO_CHOICES)
        if scenario not in valid:
            raise Http404
        return render(request, 'email_templates/editor.html', {
            'scenario': scenario,
            'scenario_label': valid[scenario],
            'is_table_scenario': scenario in TABLE_SCENARIOS,
        })


class EmailTemplateHeaderListView(View):
    def get(self, request):
        return render(request, 'email_templates/headers.html')


class EmailTemplateFooterListView(View):
    def get(self, request):
        return render(request, 'email_templates/footers.html')
