from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def org_chart(request):
    return render(request, 'orgchart/chart.html')
