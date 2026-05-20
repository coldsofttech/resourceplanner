from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def howto_index(request):
    return render(request, 'howto/index.html')


@login_required
def howto_ai(request):
    return render(request, 'howto/ai.html')


@login_required
def howto_jira(request):
    return render(request, 'howto/jira.html')


@login_required
def howto_sso(request):
    return render(request, 'howto/sso.html')


@login_required
def howto_email(request):
    return render(request, 'howto/email.html')


@login_required
def howto_jobs(request):
    return render(request, 'howto/jobs.html')


@login_required
def howto_api(request):
    return render(request, 'howto/api.html')
