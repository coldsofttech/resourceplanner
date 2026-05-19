import logging

from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Win, WinEntry, MonthlyWin, MonthlyWinSurveyNomination, TeamProductOwner
from .serializers import (
    WinSerializer, WinDetailSerializer, WinEntrySerializer,
    MonthlyWinSerializer, MonthlyWinDetailSerializer,
    MonthlyWinSurveySerializer, MonthlyWinNominationSerializer,
    TeamProductOwnerSerializer,
)
from .services import WinService, MonthlyWinService, TeamProductOwnerService
from .models import MonthlyWinSurvey

logger = logging.getLogger(__name__)


class WinViewSet(viewsets.ViewSet):

    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        result = WinService.list_wins(page=page, page_size=page_size)
        return Response({
            'results': WinSerializer(result['results'], many=True).data,
            'pagination': {
                'total_count': result['total_count'],
                'total_pages': result['total_pages'],
                'current_page': result['current_page'],
                'page_size': result['page_size'],
                'has_next': result['has_next'],
                'has_previous': result['has_previous'],
            },
        })

    def create(self, request):
        week_start = request.data.get('week_start_date')
        if not week_start:
            return Response({'week_start_date': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from datetime import datetime
            if isinstance(week_start, str):
                week_start = datetime.strptime(week_start, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'week_start_date': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Win.objects.filter(week_start_date=week_start).exists():
            return Response(
                {'week_start_date': 'A win already exists for this week.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            win = WinService.create_win(week_start, user=request.user)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(WinSerializer(win).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            win = WinService.get_win(pk)
        except Win.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(WinDetailSerializer(win).data)

    @action(detail=False, methods=['get'], url_path='next-week')
    def next_week(self, request):
        from datetime import date, timedelta
        today = date.today()
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        next_number = WinService.next_week_number()
        return Response({'week_number': next_number, 'suggested_week_start': str(monday)})

    @action(detail=True, methods=['get'], url_path='entries')
    def entries(self, request, pk=None):
        try:
            win = WinService.get_win(pk)
        except Win.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        team_id = request.query_params.get('team_id')
        qs = win.entries.select_related('team', 'created_by')
        if team_id:
            qs = qs.filter(team_id=team_id)
        return Response(WinEntrySerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='entries/add')
    def add_entry(self, request, pk=None):
        team_id = request.data.get('team')
        title = (request.data.get('title') or '').strip()
        description = (request.data.get('description') or '').strip()

        if not team_id:
            return Response({'team': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not title:
            return Response({'title': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entry = WinService.add_entry(pk, team_id, title, description, user=request.user)
        except Win.DoesNotExist:
            return Response({'detail': 'Win not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(WinEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch'], url_path=r'entries/(?P<entry_pk>\d+)')
    def update_entry(self, request, entry_pk=None):
        title = (request.data.get('title') or '').strip()
        description = request.data.get('description')

        if not title:
            return Response({'title': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entry = WinService.update_entry(entry_pk, title, description)
        except WinEntry.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(WinEntrySerializer(entry).data)

    @action(detail=False, methods=['delete'], url_path=r'entries/(?P<entry_pk>\d+)/delete')
    def delete_entry(self, request, entry_pk=None):
        WinService.delete_entry(entry_pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='review-complete')
    def review_complete(self, request, pk=None):
        try:
            win = WinService.review_complete(pk, user=request.user)
        except Win.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(WinSerializer(win).data)

    @action(detail=False, methods=['get'], url_path='report-data')
    def report_data(self, request):
        week_ids_raw = request.query_params.get('week_ids', '')
        date_from = request.query_params.get('date_from') or None
        date_to = request.query_params.get('date_to') or None

        week_ids = []
        if week_ids_raw:
            try:
                week_ids = [int(x) for x in week_ids_raw.split(',') if x.strip()]
            except ValueError:
                return Response({'week_ids': 'Must be comma-separated integers.'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime as dt
        try:
            if date_from:
                date_from = dt.strptime(date_from, '%Y-%m-%d').date()
            if date_to:
                date_to = dt.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        data = WinService.get_report_data(week_ids=week_ids or None, date_from=date_from, date_to=date_to)
        return Response(data)


class MonthlyWinViewSet(viewsets.ViewSet):

    def list(self, request):
        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        result = MonthlyWinService.list_monthly_wins(page=page, page_size=page_size)
        return Response({
            'results': MonthlyWinSerializer(result['results'], many=True).data,
            'pagination': {
                'total_count': result['total_count'],
                'total_pages': result['total_pages'],
                'current_page': result['current_page'],
                'page_size': result['page_size'],
                'has_next': result['has_next'],
                'has_previous': result['has_previous'],
            },
        })

    def create(self, request):
        name = (request.data.get('name') or '').strip()
        win_ids = request.data.get('win_ids', [])
        phase1_deadline = request.data.get('phase1_deadline')

        if not name:
            return Response({'name': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime
        if phase1_deadline:
            try:
                phase1_deadline = datetime.fromisoformat(phase1_deadline)
            except ValueError:
                return Response({'phase1_deadline': 'Invalid datetime format.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            mw = MonthlyWinService.create_monthly_win(name, win_ids, phase1_deadline, user=request.user)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinSerializer(mw).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            mw = MonthlyWinService.get_monthly_win(pk)
        except MonthlyWin.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MonthlyWinDetailSerializer(mw).data)

    def partial_update(self, request, pk=None):
        name = request.data.get('name')
        win_ids = request.data.get('win_ids')
        phase1_deadline = request.data.get('phase1_deadline')
        phase2_deadline = request.data.get('phase2_deadline')

        from datetime import datetime
        def parse_dt(val):
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                return None

        try:
            mw = MonthlyWinService.update_monthly_win(
                pk,
                name=name,
                win_ids=win_ids,
                phase1_deadline=parse_dt(phase1_deadline),
                phase2_deadline=parse_dt(phase2_deadline),
            )
        except (MonthlyWin.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWin.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinSerializer(mw).data)

    @action(detail=True, methods=['post'], url_path='launch-phase1')
    def launch_phase1(self, request, pk=None):
        try:
            mw = MonthlyWinService.launch_phase1(pk, user=request.user)
        except (MonthlyWin.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWin.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinDetailSerializer(mw).data)

    @action(detail=True, methods=['post'], url_path='complete-phase1')
    def complete_phase1(self, request, pk=None):
        try:
            mw = MonthlyWinService.complete_phase1(pk)
        except (MonthlyWin.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWin.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinDetailSerializer(mw).data)

    @action(detail=True, methods=['post'], url_path='launch-phase2')
    def launch_phase2(self, request, pk=None):
        try:
            mw = MonthlyWinService.launch_phase2(pk)
        except (MonthlyWin.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWin.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinDetailSerializer(mw).data)

    @action(detail=True, methods=['post'], url_path='declare')
    def declare_winners(self, request, pk=None):
        try:
            mw = MonthlyWinService.declare_winners(pk)
        except (MonthlyWin.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWin.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinDetailSerializer(mw).data)

    @action(detail=True, methods=['get'], url_path='phase1-nominations')
    def phase1_nominations(self, request, pk=None):
        nominations = MonthlyWinService.get_phase1_nominations(pk)
        return Response(MonthlyWinNominationSerializer(nominations, many=True).data)

    @action(detail=False, methods=['post'], url_path=r'surveys/(?P<survey_pk>\d+)/remind')
    def remind_survey(self, request, survey_pk=None):
        try:
            survey = MonthlyWinService.send_reminder(survey_pk)
        except (MonthlyWinSurvey.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWinSurvey.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinSurveySerializer(survey).data)

    @action(detail=False, methods=['post'], url_path=r'surveys/(?P<survey_pk>\d+)/override')
    def override_survey(self, request, survey_pk=None):
        try:
            survey = MonthlyWinService.override_survey(survey_pk)
        except (MonthlyWinSurvey.DoesNotExist, ValidationError) as exc:
            if isinstance(exc, MonthlyWinSurvey.DoesNotExist):
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinSurveySerializer(survey).data)

    @action(detail=False, methods=['post'], url_path=r'nominations/(?P<nom_pk>\d+)/dismiss')
    def dismiss_nomination(self, request, nom_pk=None):
        reason = (request.data.get('reason') or '').strip()
        try:
            nom = MonthlyWinService.dismiss_nomination(nom_pk, reason)
        except MonthlyWinSurveyNomination.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MonthlyWinNominationSerializer(nom).data)

    @action(detail=False, methods=['post'], url_path=r'nominations/(?P<nom_pk>\d+)/undismiss')
    def undismiss_nomination(self, request, nom_pk=None):
        try:
            nom = MonthlyWinService.undismiss_nomination(nom_pk)
        except MonthlyWinSurveyNomination.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(MonthlyWinNominationSerializer(nom).data)

    # ── Preview endpoints ────────────────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='preview-teams')
    def preview_teams(self, request, pk=None):
        """Return teams that have entries in selected weeks — for Phase 1 preview dropdown."""
        try:
            teams = MonthlyWinService.get_teams_for_preview(pk)
            return Response(teams)
        except MonthlyWin.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], url_path='preview-survey')
    def preview_survey(self, request, pk=None):
        """Preview the survey form before launching a phase."""
        phase = request.query_params.get('phase', MonthlyWinSurvey.PHASE_1)
        team_id = request.query_params.get('team_id') or None
        try:
            data = MonthlyWinService.get_preview_survey_data(pk, phase, team_id)
            return Response(data)
        except MonthlyWin.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ── Admin override form ──────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path=r'surveys/(?P<survey_pk>\d+)/survey-data')
    def survey_data_for_admin(self, request, survey_pk=None):
        """Return survey data so admin can fill in on behalf of a PO."""
        try:
            data = MonthlyWinService.get_admin_survey_data(survey_pk)
            return Response(data)
        except MonthlyWinSurvey.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path=r'surveys/(?P<survey_pk>\d+)/override-submit')
    def override_survey_submit(self, request, survey_pk=None):
        """Admin submits nominations and marks survey as overridden."""
        nominations_data = request.data.get('nominations', [])
        try:
            survey = MonthlyWinService.override_survey_with_nominations(survey_pk, nominations_data)
        except MonthlyWinSurvey.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response(
                exc.message_dict if hasattr(exc, 'message_dict') else {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonthlyWinSurveySerializer(survey).data)


class TeamProductOwnerViewSet(viewsets.ViewSet):

    def list(self, request):
        team_id = request.query_params.get('team_id')
        if team_id:
            qs = TeamProductOwnerService.list_for_team(team_id)
        else:
            qs = TeamProductOwnerService.list_all()
        return Response(TeamProductOwnerSerializer(qs, many=True).data)

    def create(self, request):
        team_id = request.data.get('team')
        user_id = request.data.get('user')
        if not team_id or not user_id:
            return Response({'detail': 'team and user are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tpo = TeamProductOwnerService.add(team_id, user_id)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TeamProductOwnerSerializer(tpo).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        TeamProductOwnerService.remove(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
