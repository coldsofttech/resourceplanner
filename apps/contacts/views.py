from django.shortcuts import render
from django.views.generic import View


class ContactListView(View):
    template_name = "contacts/contact_list.html"

    def get(self, request):
        return render(request, self.template_name)
