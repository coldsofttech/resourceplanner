from django.shortcuts import render
from django.views.generic import View


class ImportView(View):
    """
    Import view for all the modules.
    """
    template_name = 'import/import.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
