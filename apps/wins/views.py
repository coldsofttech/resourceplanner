from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import MonthlyWin, MonthlyWinSurvey
from .services import MonthlyWinService


@login_required
def wins_list(request):
    return render(request, 'wins/list.html')


@login_required
def win_detail(request, pk):
    return render(request, 'wins/detail.html', {'win_pk': pk})


@login_required
def wins_report(request):
    return render(request, 'wins/report.html')


@login_required
def monthly_wins_list(request):
    return render(request, 'wins/monthly_list.html')


@login_required
def monthly_win_detail(request, pk):
    mw = get_object_or_404(MonthlyWin, pk=pk)
    return render(request, 'wins/monthly_detail.html', {'monthly_win_pk': pk, 'monthly_win': mw})


@login_required
def monthly_win_report(request, pk):
    mw = get_object_or_404(MonthlyWin, pk=pk)
    return render(request, 'wins/monthly_report.html', {'monthly_win': mw, 'monthly_win_pk': pk})


@login_required
def product_owners(request):
    return render(request, 'wins/product_owners.html')


def monthly_win_survey(request, token):
    """Token-based survey page — no login required."""
    try:
        data = MonthlyWinService.get_survey_data(token)
    except MonthlyWinSurvey.DoesNotExist:
        return render(request, 'wins/survey_invalid.html', status=404)

    survey = data['survey']

    if request.method == 'POST' and survey.status == MonthlyWinSurvey.STATUS_PENDING:
        from django.core.exceptions import ValidationError
        import json

        nominations_raw = request.POST.getlist('nominations')
        nominations_data = []
        for raw in nominations_raw:
            try:
                item = json.loads(raw)
                nominations_data.append({'entry_id': int(item['entry_id']), 'category': item['category']})
            except (ValueError, KeyError, TypeError):
                pass

        try:
            MonthlyWinService.submit_survey(token, nominations_data)
            return render(request, 'wins/survey_thankyou.html', {'survey': survey})
        except ValidationError as exc:
            data['error'] = str(exc)
            return render(request, 'wins/survey.html', data)

    return render(request, 'wins/survey.html', data)
