from django.shortcuts import render
from django.views.generic import ListView, View

from .models import MemberLeave


class MemberLeaveListView(ListView):
    model = MemberLeave
    template_name = 'member_leaves/leave_list.html'


class MemberLeaveCreateView(View):
    template_name = 'member_leaves/leave_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class MemberLeaveDetailView(View):
    template_name = 'member_leaves/leave_detail.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class MemberLeaveUpdateView(View):
    template_name = 'member_leaves/leave_form.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
