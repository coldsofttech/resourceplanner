import logging
from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import (
    IMPORT_STATUS_ACTIVE,
    IMPORT_STATUS_CONFIRMED,
    IMPORT_TYPE_FORECAST,
    IMPORT_TYPE_ACTUAL,
    RECHARGE_TYPE_FORECAST,
    RECHARGE_TYPE_ACTUAL,
    RECHARGE_EMAIL_STATUS_PENDING,
    RECHARGE_EMAIL_STATUS_SENT,
    RECHARGE_EMAIL_STATUS_ERROR,
    ProjectActuals,
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    ProjectSprintActual,
    Recharge,
    RechargeDetail,
    RechargeEmail,
    RechargeProjectGroup,
    SprintConfirmedRow,
    SprintImport,
    SprintImportReviewComplete,
    SprintImportRow,
)
from .serializers import (
    ImportReviewSerializer,
    ProjectActualsSerializer,
    ProjectFinanceTypeMappingSerializer,
    ProjectFinanceTypeSerializer,
    RechargeDetailSerializer,
    RechargeEmailSerializer,
    RechargeProjectGroupSerializer,
    RechargeSerializer,
    SprintConfirmedRowSerializer,
    SprintImportReviewCompleteSerializer,
    SprintImportRowSerializer,
    SprintImportSerializer,
)
from .services import (
    ImportConfirmService,
    ImportReviewCompleteService,
    ImportReviewService,
    SprintImportService,
)

logger = logging.getLogger(__name__)


class ProjectFinanceTypeViewSet(viewsets.ViewSet):

    def list(self, request):
        try:
            qs = ProjectFinanceType.objects.all()
            active_only = request.query_params.get('active_only', 'false').lower() == 'true'
            if active_only:
                qs = qs.filter(is_active=True)
            return Response(ProjectFinanceTypeSerializer(qs, many=True).data)
        except Exception as e:
            logger.exception('Error listing finance types: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        s = ProjectFinanceTypeSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = s.save()
            return Response(ProjectFinanceTypeSerializer(obj).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception('Error creating finance type: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            obj = ProjectFinanceType.objects.get(pk=pk)
        except ProjectFinanceType.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectFinanceTypeSerializer(obj).data)

    def partial_update(self, request, pk=None):
        try:
            obj = ProjectFinanceType.objects.get(pk=pk)
        except ProjectFinanceType.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        s = ProjectFinanceTypeSerializer(obj, data=request.data, partial=True)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        obj = s.save()
        return Response(ProjectFinanceTypeSerializer(obj).data)

    def destroy(self, request, pk=None):
        try:
            obj = ProjectFinanceType.objects.get(pk=pk)
        except ProjectFinanceType.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='options')
    def options(self, request):
        qs = ProjectFinanceType.objects.filter(is_active=True).values('id', 'code', 'name')
        return Response(list(qs))


class ProjectFinanceTypeMappingViewSet(viewsets.ViewSet):

    def list(self, request):
        qs = ProjectFinanceTypeMapping.objects.select_related('project_type', 'finance_type').all()
        pt_id = request.query_params.get('project_type_id')
        if pt_id:
            qs = qs.filter(project_type_id=pt_id)
        return Response(ProjectFinanceTypeMappingSerializer(qs, many=True).data)

    def create(self, request):
        s = ProjectFinanceTypeMappingSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = s.save()
            return Response(ProjectFinanceTypeMappingSerializer(obj).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception('Error creating mapping: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, pk=None):
        try:
            obj = ProjectFinanceTypeMapping.objects.get(pk=pk)
        except ProjectFinanceTypeMapping.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _sprint_locked_response():
    return Response({'error': 'This sprint is closed and locked. Ask an admin to unlock it.'}, status=status.HTTP_423_LOCKED)


def _is_sprint_locked(sprint_id):
    from apps.sprints.models import Sprint
    try:
        return Sprint.objects.filter(pk=sprint_id, is_closed=True).exists()
    except Exception:
        return False


class BaseSprintImportViewSet(viewsets.ViewSet):
    """Shared logic for forecast and actuals import endpoints.

    Subclasses set ``import_type`` to ``IMPORT_TYPE_FORECAST`` or ``IMPORT_TYPE_ACTUAL``.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    import_type = IMPORT_TYPE_FORECAST  # overridden by subclasses

    def list(self, request):
        sprint_id = request.query_params.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            team_id = request.query_params.get('team_id')
            qs = SprintImportService.list_imports(sprint_id, team_id, import_type=self.import_type)
            return Response(SprintImportSerializer(qs, many=True).data)
        except Exception as e:
            logger.exception('Error listing imports: %s', e)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        sprint_id = request.data.get('sprint_id')
        team_id = request.data.get('team_id')
        csv_file = request.FILES.get('file')

        if not sprint_id or not team_id:
            return Response({'error': 'sprint_id and team_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if _is_sprint_locked(sprint_id):
            return _sprint_locked_response()
        if not csv_file:
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)
        if not csv_file.name.lower().endswith('.csv'):
            return Response({'error': 'Only CSV files are accepted.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            fi = SprintImportService.import_csv(
                sprint_id=sprint_id,
                team_id=team_id,
                csv_file=csv_file,
                user=request.user,
                import_type=self.import_type,
            )
            return Response(SprintImportSerializer(fi).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception('Error importing CSV: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            fi = SprintImport.objects.select_related('sprint', 'team', 'imported_by').get(
                pk=pk, import_type=self.import_type,
            )
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SprintImportSerializer(fi).data)

    @action(detail=True, methods=['get'], url_path='rows')
    def rows(self, request, pk=None):
        try:
            fi = SprintImport.objects.select_related('sprint').get(pk=pk, import_type=self.import_type)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        qs = fi.rows.select_related(
            'assignee', 'assignee_override',
            'label', 'label_override',
            'mapping', 'mapping_override',
        ).prefetch_related('review_results__review').order_by('order')
        rows_data = SprintImportRowSerializer(qs, many=True).data

        from apps.sprint_capacity.models import SprintCapacity
        member_capacities = {}
        for sc in SprintCapacity.objects.filter(sprint_id=fi.sprint_id).select_related('team_member'):
            if sc.team_member:
                member_capacities[sc.team_member.display_name] = float(sc.net_capacity)

        return Response({'rows': list(rows_data), 'member_capacities': member_capacities})

    @action(detail=True, methods=['patch'], url_path='rows/(?P<row_id>[0-9]+)')
    def update_row(self, request, pk=None, row_id=None):
        try:
            fi = SprintImport.objects.get(pk=pk, import_type=self.import_type)
            row = SprintImportRow.objects.get(pk=row_id, sprint_import=fi)
        except (SprintImport.DoesNotExist, SprintImportRow.DoesNotExist):
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if _is_sprint_locked(fi.sprint_id):
            return _sprint_locked_response()

        for field in ('story_type_override', 'jira_id_override', 'title_override',
                      'assignee_raw_override', 'sprint_name_override'):
            if field in request.data:
                val = request.data[field]
                setattr(row, field, val if val not in ('', None) else None)

        if 'efforts_ms_override' in request.data:
            val = request.data['efforts_ms_override']
            try:
                row.efforts_ms_override = int(float(val)) if val not in ('', None) else None
            except (ValueError, TypeError):
                row.efforts_ms_override = None

        if 'mapping_override' in request.data:
            val = request.data['mapping_override']
            if not val:
                row.mapping_override = None
            else:
                try:
                    row.mapping_override = ProjectFinanceType.objects.get(pk=val)
                except ProjectFinanceType.DoesNotExist:
                    return Response({'error': f'Finance type {val} not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if 'label_override_raw' in request.data:
            from apps.projects.models import ProjectLabel
            raw = (request.data['label_override_raw'] or '').strip()
            row.label_override = ProjectLabel.objects.filter(label__iexact=raw).first() if raw else None

        if 'assignee_raw_override' in request.data:
            from .services import _match_assignee
            row.assignee_override = _match_assignee(request.data['assignee_raw_override'])

        row.save()

        fi.refresh_from_db(fields=['status'])
        if fi.status == IMPORT_STATUS_CONFIRMED:
            recharge_type = RECHARGE_TYPE_ACTUAL if self.import_type == IMPORT_TYPE_ACTUAL else RECHARGE_TYPE_FORECAST
            fi.status = IMPORT_STATUS_ACTIVE
            fi.save(update_fields=['status'])
            SprintConfirmedRow.objects.filter(
                sprint_id=fi.sprint_id, team_id=fi.team_id, import_type=self.import_type,
            ).delete()
            RechargeDetail.objects.filter(
                sprint_id=fi.sprint_id, team_id=fi.team_id, type=recharge_type,
            ).delete()

        return Response(SprintImportRowSerializer(row).data)

    @action(detail=True, methods=['post'], url_path='add-row')
    def add_row(self, request, pk=None):
        try:
            fi = SprintImport.objects.get(pk=pk, import_type=self.import_type)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if _is_sprint_locked(fi.sprint_id):
            return _sprint_locked_response()

        last_order = fi.rows.order_by('-order').values_list('order', flat=True).first() or 0
        data = request.data.copy()
        data['sprint_import'] = fi.id
        data['order'] = last_order + 1
        data['is_manually_added'] = True

        s = SprintImportRowSerializer(data=data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        row = s.save()
        return Response(SprintImportRowSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='rows/(?P<row_id>[0-9]+)/delete')
    def delete_row(self, request, pk=None, row_id=None):
        try:
            fi = SprintImport.objects.get(pk=pk, import_type=self.import_type)
            row = SprintImportRow.objects.get(pk=row_id, sprint_import=fi)
        except (SprintImport.DoesNotExist, SprintImportRow.DoesNotExist):
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if _is_sprint_locked(fi.sprint_id):
            return _sprint_locked_response()
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, pk=None):
        try:
            rev = ImportReviewService.run_review(pk, user=request.user)
            return Response(ImportReviewSerializer(rev).data, status=status.HTTP_201_CREATED)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception('Error running review: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='reviews')
    def reviews(self, request, pk=None):
        try:
            fi = SprintImport.objects.get(pk=pk, import_type=self.import_type)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        qs = fi.reviews.prefetch_related('results').order_by('-reviewed_at')
        return Response(ImportReviewSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        try:
            fi = SprintImport.objects.get(pk=pk, import_type=self.import_type)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if _is_sprint_locked(fi.sprint_id):
            return _sprint_locked_response()
        try:
            fi = ImportConfirmService.confirm(pk, user=request.user)
            return Response(SprintImportSerializer(fi).data)
        except SprintImport.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Error confirming import: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='labels-options')
    def labels_options(self, request):
        from apps.projects.models import ProjectLabel
        qs = ProjectLabel.objects.select_related('project').order_by('project__name', 'label')
        return Response([
            {'id': lbl.id, 'label': lbl.label, 'project_name': lbl.project.name if lbl.project else ''}
            for lbl in qs
        ])

    @action(detail=False, methods=['get'], url_path='sprint-status')
    def sprint_status(self, request):
        sprint_id = request.query_params.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            team_statuses = SprintImportService.get_sprint_teams_status(sprint_id, import_type=self.import_type)
            result = [
                {
                    'team_id': ts['team'].id,
                    'team_name': ts['team'].name,
                    'has_imports': ts['has_imports'],
                    'confirmed': ts['confirmed'],
                    'latest_import': SprintImportSerializer(ts['latest_import']).data if ts['latest_import'] else None,
                    'versions': SprintImportSerializer(ts['versions'], many=True).data,
                }
                for ts in team_statuses
            ]
            try:
                rc = SprintImportReviewComplete.objects.get(sprint_id=sprint_id, import_type=self.import_type)
                rc_data = SprintImportReviewCompleteSerializer(rc).data
            except SprintImportReviewComplete.DoesNotExist:
                rc_data = None
            return Response({'teams': result, 'review_complete': rc_data})
        except Exception as e:
            logger.exception('Error getting sprint status: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='review-warnings')
    def review_warnings(self, request):
        sprint_id = request.query_params.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            warnings = ImportReviewCompleteService.check_warnings(sprint_id, import_type=self.import_type)
            return Response({'warnings': warnings, 'has_warnings': bool(warnings)})
        except Exception as e:
            logger.exception('Error checking warnings: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='review-complete')
    def review_complete(self, request):
        sprint_id = request.data.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if _is_sprint_locked(sprint_id):
            return _sprint_locked_response()
        override = request.data.get('override', False)
        override_notes = request.data.get('override_notes', '')

        if not override:
            warnings = ImportReviewCompleteService.check_warnings(sprint_id, import_type=self.import_type)
            if warnings:
                return Response(
                    {'warnings': warnings, 'has_warnings': True,
                     'detail': 'Warnings found. Pass override=true to proceed.'},
                    status=status.HTTP_409_CONFLICT,
                )
        try:
            ImportReviewCompleteService.complete(
                sprint_id=sprint_id,
                user=request.user,
                override=override,
                override_notes=override_notes,
                import_type=self.import_type,
            )
            rc = SprintImportReviewComplete.objects.get(sprint_id=sprint_id, import_type=self.import_type)
            return Response(SprintImportReviewCompleteSerializer(rc).data)
        except Exception as e:
            logger.exception('Error completing review: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SprintForecastViewSet(BaseSprintImportViewSet):
    import_type = IMPORT_TYPE_FORECAST


class SprintActualsViewSet(BaseSprintImportViewSet):
    import_type = IMPORT_TYPE_ACTUAL


class SprintConfirmedRowViewSet(viewsets.ViewSet):

    def list(self, request):
        sprint_id = request.query_params.get('sprint_id')
        team_id = request.query_params.get('team_id')
        import_type = request.query_params.get('import_type', '').upper() or None
        qs = SprintConfirmedRow.objects.select_related('sprint', 'team', 'assignee', 'label', 'mapping')
        if sprint_id:
            qs = qs.filter(sprint_id=sprint_id)
        if team_id:
            qs = qs.filter(team_id=team_id)
        if import_type in (IMPORT_TYPE_FORECAST, IMPORT_TYPE_ACTUAL):
            qs = qs.filter(import_type=import_type)
        return Response(SprintConfirmedRowSerializer(qs, many=True).data)


import html as _html_module


def _esc(s):
    return _html_module.escape(str(s or ''))


def _build_recharge_email_entries(sprint_id, recharge_type):
    """Build email entry dicts for trigger/review endpoints."""
    from decimal import Decimal, ROUND_HALF_UP
    from apps.configurations.services import ConfigurationService
    from apps.projects.services import ProjectCodeService

    recharges = list(
        Recharge.objects
        .filter(sprint_id=sprint_id, type=recharge_type)
        .select_related('sprint', 'sprint__financial_year', 'programme', 'project')
        .prefetch_related('stories', 'finance_contacts__contact', 'project_contacts__contact')
    )
    if not recharges:
        return []

    sprint = recharges[0].sprint
    sprint_name = sprint.sprint_name
    fy_short = sprint.financial_year.short_fy if hasattr(sprint, 'financial_year') and sprint.financial_year else ''
    type_label = 'Forecast' if recharge_type == RECHARGE_TYPE_FORECAST else 'Actuals'
    verb = 'planned' if recharge_type == RECHARGE_TYPE_FORECAST else 'completed'
    subject = f'Recharge Approval Request — {sprint_name} ({fy_short}) — {type_label}'

    price = Decimal(str(ConfigurationService.get_float('SPRINT_POINT_PRICE', 0.0)))

    all_groups = list(RechargeProjectGroup.objects.prefetch_related('projects').all())
    project_group_map = {}
    for grp in all_groups:
        for proj in grp.projects.all():
            project_group_map[proj.id] = grp

    grouped = {}
    ungrouped = []
    for r in recharges:
        pid = r.project_id
        if pid and pid in project_group_map:
            grp = project_group_map[pid]
            if grp.id not in grouped:
                grouped[grp.id] = {'group': grp, 'recharges': []}
            grouped[grp.id]['recharges'].append(r)
        else:
            ungrouped.append(r)

    def _project_data(r):
        pc = None
        if r.project_id:
            try:
                active = ProjectCodeService.get_active(r.project_id)
                pc = active.code if active else None
            except Exception:
                pass
        stories = []
        for s in r.stories.all():
            cost = (s.total_days * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            stories.append({
                'jira_id': s.jira_id,
                'title': s.title,
                'total_days': str(s.total_days),
                'cost': str(cost),
            })
        return {
            'id': r.project_id,
            'name': r.project.name if r.project else '—',
            'programme_name': r.programme.name if r.programme else '—',
            'project_code': pc,
            'total_days': str(r.total_days),
            'total_cost': str(r.total_cost),
            'stories': stories,
        }

    def _body_html(projects_data):
        projects_html = ''
        for p in projects_data:
            rows = ''.join(
                f'<tr><td>{_esc(s["jira_id"])}</td><td>{_esc(s["title"])}</td>'
                f'<td align="right">{s["total_days"]}</td>'
                f'<td align="right">£{float(s["cost"]):,.2f}</td></tr>'
                for s in p['stories']
            )
            pc = _esc(p['project_code'] or '—')
            projects_html += (
                f'<h3 style="margin-top:24px;font-size:16px">{_esc(p["name"])} ({_esc(p["programme_name"])})</h3>'
                f'<p>Project Code to be charged: <strong>{pc}</strong></p>'
                f'<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:14px">'
                f'<thead style="background:#f0f0f0"><tr>'
                f'<th align="left">Jira ID</th><th align="left">Title / Description</th>'
                f'<th align="right">Days</th><th align="right">Cost (£)</th>'
                f'</tr></thead><tbody>{rows}'
                f'<tr style="font-weight:bold;background:#f9f9f9">'
                f'<td colspan="2">Total</td>'
                f'<td align="right">{p["total_days"]}</td>'
                f'<td align="right">£{float(p["total_cost"]):,.2f}</td>'
                f'</tr></tbody></table>'
            )
        return (
            f'<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#333;max-width:800px;margin:0 auto;padding:20px">'
            f'<p>Dear Team,</p>'
            f'<p>We are writing to request your approval for the {verb} Jira stories for '
            f'<strong>{_esc(sprint_name)}</strong> ({_esc(fy_short)}).</p>'
            f'{projects_html}'
            f'<p style="margin-top:24px">Please review and respond within <strong>48 hours</strong> to confirm your approval.</p>'
            f'<p>Kind regards,<br>Resource Planning Team</p>'
            f'</body></html>'
        )

    def _latest_email(grp_id, proj_id):
        qs = RechargeEmail.objects.filter(sprint_id=sprint_id, type=recharge_type)
        if grp_id:
            qs = qs.filter(group_id=grp_id)
        else:
            qs = qs.filter(group__isnull=True, project_id=proj_id)
        return qs.order_by('-triggered_at').first()

    entries = []

    for gid, data in grouped.items():
        grp = data['group']
        to_emails = set()
        for r in data['recharges']:
            for c in r.finance_contacts.all():
                if c.contact.email:
                    to_emails.add(c.contact.email)
            for c in r.project_contacts.all():
                if c.contact.email:
                    to_emails.add(c.contact.email)
        projects_data = [_project_data(r) for r in data['recharges']]
        total_days = sum(Decimal(p['total_days']) for p in projects_data)
        total_cost = sum(Decimal(p['total_cost']) for p in projects_data)
        le = _latest_email(gid, None)
        entries.append({
            'entry_key': f'group_{gid}',
            'group_id': gid,
            'group_name': grp.name,
            'total_days': str(total_days),
            'total_cost': str(total_cost),
            'to_emails': sorted(to_emails),
            'cc_emails': [],
            'subject': subject,
            'projects': projects_data,
            'body_html': _body_html(projects_data),
            'email_status': le.status if le else None,
            'last_sent_at': le.sent_at.isoformat() if le and le.sent_at else None,
        })

    for r in ungrouped:
        to_emails = set()
        for c in r.finance_contacts.all():
            if c.contact.email:
                to_emails.add(c.contact.email)
        for c in r.project_contacts.all():
            if c.contact.email:
                to_emails.add(c.contact.email)
        p_data = _project_data(r)
        le = _latest_email(None, r.project_id)
        entries.append({
            'entry_key': f'project_{r.project_id or r.id}',
            'group_id': None,
            'group_name': None,
            'total_days': str(r.total_days),
            'total_cost': str(r.total_cost),
            'to_emails': sorted(to_emails),
            'cc_emails': [],
            'subject': subject,
            'projects': [p_data],
            'body_html': _body_html([p_data]),
            'email_status': le.status if le else None,
            'last_sent_at': le.sent_at.isoformat() if le and le.sent_at else None,
        })

    return entries


class RechargeViewSet(viewsets.ViewSet):

    def list(self, request):
        qs = Recharge.objects.select_related(
            'sprint', 'programme', 'project'
        ).prefetch_related('stories', 'finance_contacts__contact', 'project_contacts__contact')
        sprint_id = request.query_params.get('sprint_id')
        type_filter = request.query_params.get('type')
        project_id = request.query_params.get('project_id')
        programme_id = request.query_params.get('programme_id')
        fy_id = request.query_params.get('fy_id')
        if fy_id:
            qs = qs.filter(sprint__financial_year_id=fy_id)
        if sprint_id:
            qs = qs.filter(sprint_id=sprint_id)
        if type_filter:
            qs = qs.filter(type=type_filter.upper())
        if project_id:
            qs = qs.filter(project_id=project_id)
        if programme_id:
            qs = qs.filter(programme_id=programme_id)
        return Response(RechargeSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            obj = Recharge.objects.select_related(
                'sprint', 'programme', 'project'
            ).prefetch_related('stories', 'finance_contacts__contact', 'project_contacts__contact').get(pk=pk)
        except Recharge.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RechargeSerializer(obj).data)

    @action(detail=False, methods=['get'], url_path='programme-options')
    def programme_options(self, request):
        from apps.programmes.models import Programme
        qs = Programme.objects.filter(is_active=True).values('id', 'name').order_by('name')
        return Response(list(qs))

    @action(detail=False, methods=['get'], url_path='project-options')
    def project_options(self, request):
        from apps.projects.models import Project
        qs = Project.objects.values('id', 'name').order_by('name')
        return Response(list(qs))

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        from decimal import Decimal, ROUND_HALF_UP
        from django.db.models import Sum
        from apps.configurations.services import ConfigurationService

        sprint_id = request.query_params.get('sprint_id')
        recharge_type = request.query_params.get('type', '').upper()
        if not sprint_id:
            return Response({'error': 'sprint_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        def _q(rtype):
            return Recharge.objects.filter(sprint_id=sprint_id, type=rtype)

        recharges = _q(recharge_type)
        exists = recharges.exists()
        raw_total = recharges.aggregate(t=Sum('total_cost'))['t'] or Decimal('0')
        raw_days = recharges.aggregate(t=Sum('total_days'))['t'] or Decimal('0')
        total_cost = Decimal(str(raw_total)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_days = Decimal(str(raw_days))

        price = Decimal(str(ConfigurationService.get_float('SPRINT_POINT_PRICE', 0.0)))
        ft_days = {}
        if exists:
            ft_rows = (
                SprintConfirmedRow.objects
                .filter(sprint_id=sprint_id, import_type=recharge_type, mapping__isnull=False)
                .values('mapping_id')
                .annotate(td=Sum('days'))
            )
            ft_days = {r['mapping_id']: Decimal(str(r['td'] or 0)) for r in ft_rows}

        all_fts = ProjectFinanceType.objects.filter(is_active=True).order_by('code')
        finance_breakdown = []
        for ft in all_fts:
            days = ft_days.get(ft.id, Decimal('0'))
            cost = (days * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            finance_breakdown.append({
                'id': ft.id,
                'code': ft.code,
                'name': ft.name,
                'days': str(days),
                'cost': str(cost),
            })

        forecast_exists = _q(RECHARGE_TYPE_FORECAST).exists()
        actual_exists = _q(RECHARGE_TYPE_ACTUAL).exists()
        combined = {'has_forecast': forecast_exists, 'has_actual': actual_exists}
        if forecast_exists and actual_exists:
            ft = Decimal(str(_q(RECHARGE_TYPE_FORECAST).aggregate(t=Sum('total_cost'))['t'] or 0))
            at = Decimal(str(_q(RECHARGE_TYPE_ACTUAL).aggregate(t=Sum('total_cost'))['t'] or 0))
            combined.update({
                'forecast_total': str(ft.quantize(Decimal('0.01'))),
                'actual_total': str(at.quantize(Decimal('0.01'))),
                'variance': str((at - ft).quantize(Decimal('0.01'))),
            })

        return Response({
            'exists': exists,
            'total_cost': str(total_cost),
            'total_days': str(total_days),
            'finance_type_breakdown': finance_breakdown,
            'combined': combined,
        })

    @action(detail=False, methods=['get'], url_path='email-review')
    def email_review(self, request):
        sprint_id = request.query_params.get('sprint_id')
        recharge_type = request.query_params.get('type', '').upper()
        if not sprint_id:
            return Response({'error': 'sprint_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            entries = _build_recharge_email_entries(sprint_id, recharge_type)
            for e in entries:
                e.pop('body_html', None)
            return Response(entries)
        except Exception as exc:
            logger.exception('Error building email review: %s', exc)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='trigger-emails')
    def trigger_emails(self, request):
        from django.core.mail import EmailMessage
        from django.utils import timezone as tz
        from apps.configurations.services import ConfigurationService

        sprint_id = request.data.get('sprint_id')
        recharge_type = request.data.get('type', '').upper()
        if not sprint_id or not recharge_type:
            return Response({'error': 'sprint_id and type required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entries = _build_recharge_email_entries(sprint_id, recharge_type)
        except Exception as exc:
            logger.exception('Error building email entries: %s', exc)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not entries:
            return Response({'error': 'No recharges found for this sprint/type.'}, status=status.HTTP_404_NOT_FOUND)

        from_email = ConfigurationService.get_str('EMAIL_FROM', '') or None
        results = []
        for entry in entries:
            rec = RechargeEmail.objects.create(
                sprint_id=sprint_id,
                type=recharge_type,
                group_id=entry.get('group_id'),
                project_id=(entry['projects'][0]['id'] if not entry.get('group_id') and entry['projects'] else None),
                to_emails=entry['to_emails'],
                cc_emails=entry['cc_emails'],
                subject=entry['subject'],
                body=entry['body_html'],
                status=RECHARGE_EMAIL_STATUS_PENDING,
                triggered_by=request.user,
            )
            if entry['to_emails']:
                try:
                    msg = EmailMessage(
                        subject=entry['subject'],
                        body=entry['body_html'],
                        from_email=from_email,
                        to=entry['to_emails'],
                        cc=entry['cc_emails'] or [],
                    )
                    msg.content_subtype = 'html'
                    msg.send()
                    rec.status = RECHARGE_EMAIL_STATUS_SENT
                    rec.sent_at = tz.now()
                except Exception as exc:
                    rec.status = RECHARGE_EMAIL_STATUS_ERROR
                    rec.error_message = str(exc)[:500]
            else:
                rec.status = RECHARGE_EMAIL_STATUS_ERROR
                rec.error_message = 'No recipient email addresses found.'
            rec.save(update_fields=['status', 'sent_at', 'error_message'])
            results.append({
                'entry_key': entry['entry_key'],
                'status': rec.status,
                'error_message': rec.error_message,
            })

        return Response({'results': results, 'count': len(results)})

    @action(detail=False, methods=['get'], url_path='email-status')
    def email_status(self, request):
        sprint_id = request.query_params.get('sprint_id')
        recharge_type = request.query_params.get('type')
        qs = RechargeEmail.objects.select_related('sprint', 'group', 'project', 'triggered_by')
        if sprint_id:
            qs = qs.filter(sprint_id=sprint_id)
        if recharge_type:
            qs = qs.filter(type=recharge_type.upper())
        return Response(RechargeEmailSerializer(qs, many=True).data)


class RechargeProjectGroupViewSet(viewsets.ViewSet):

    def list(self, request):
        qs = RechargeProjectGroup.objects.prefetch_related('projects').all()
        return Response(RechargeProjectGroupSerializer(qs, many=True).data)

    def create(self, request):
        name = request.data.get('name', '').strip()
        project_ids = request.data.get('project_ids', [])
        if not name:
            return Response({'error': 'name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if RechargeProjectGroup.objects.filter(name=name).exists():
            return Response({'error': 'A group with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from apps.projects.models import Project
            grp = RechargeProjectGroup.objects.create(name=name, created_by=request.user)
            if project_ids:
                grp.projects.set(Project.objects.filter(id__in=project_ids))
            return Response(RechargeProjectGroupSerializer(grp).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('Error creating recharge project group: %s', exc)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        try:
            grp = RechargeProjectGroup.objects.prefetch_related('projects').get(pk=pk)
        except RechargeProjectGroup.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RechargeProjectGroupSerializer(grp).data)

    def partial_update(self, request, pk=None):
        try:
            grp = RechargeProjectGroup.objects.prefetch_related('projects').get(pk=pk)
        except RechargeProjectGroup.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        name = request.data.get('name')
        project_ids = request.data.get('project_ids')
        if name is not None:
            name = name.strip()
            if not name:
                return Response({'error': 'name cannot be blank.'}, status=status.HTTP_400_BAD_REQUEST)
            if RechargeProjectGroup.objects.filter(name=name).exclude(pk=pk).exists():
                return Response({'error': 'A group with this name already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            grp.name = name
            grp.save(update_fields=['name', 'updated_at'])
        if project_ids is not None:
            from apps.projects.models import Project
            grp.projects.set(Project.objects.filter(id__in=project_ids))
        return Response(RechargeProjectGroupSerializer(grp).data)

    def destroy(self, request, pk=None):
        try:
            grp = RechargeProjectGroup.objects.get(pk=pk)
        except RechargeProjectGroup.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        grp.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='project-options')
    def project_options(self, request):
        from apps.projects.models import Project
        qs = Project.objects.values('id', 'name').order_by('name')
        return Response(list(qs))


class RechargeDetailViewSet(viewsets.ViewSet):

    def list(self, request):
        qs = RechargeDetail.objects.select_related('sprint', 'team', 'assignee', 'programme', 'project', 'label')
        sprint_id = request.query_params.get('sprint_id')
        team_id = request.query_params.get('team_id')
        type_filter = request.query_params.get('type')
        project_id = request.query_params.get('project_id')
        programme_id = request.query_params.get('programme_id')
        fy_id = request.query_params.get('fy_id')
        if fy_id:
            qs = qs.filter(sprint__financial_year_id=fy_id)
        if sprint_id:
            qs = qs.filter(sprint_id=sprint_id)
        if team_id:
            qs = qs.filter(team_id=team_id)
        if type_filter:
            qs = qs.filter(type=type_filter.upper())
        if project_id:
            qs = qs.filter(project_id=project_id)
        if programme_id:
            qs = qs.filter(programme_id=programme_id)
        return Response(RechargeDetailSerializer(qs, many=True).data)


class SprintCompareViewSet(viewsets.ViewSet):

    def list(self, request):
        sprint_id = request.query_params.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            forecast_rc = SprintImportReviewComplete.objects.filter(
                sprint_id=sprint_id, import_type=IMPORT_TYPE_FORECAST
            ).first()
            actual_rc = SprintImportReviewComplete.objects.filter(
                sprint_id=sprint_id, import_type=IMPORT_TYPE_ACTUAL
            ).first()

            forecast_complete = forecast_rc is not None
            actual_complete = actual_rc is not None
            can_compare = forecast_complete and actual_complete

            if not can_compare:
                return Response({
                    'forecast_complete': forecast_complete,
                    'actual_complete': actual_complete,
                    'can_compare': False,
                    'rows': [],
                    'summary': {},
                })

            base_qs = SprintConfirmedRow.objects.filter(sprint_id=sprint_id).select_related(
                'team', 'assignee', 'label__project__programme', 'mapping'
            )
            forecast_rows = list(base_qs.filter(import_type=IMPORT_TYPE_FORECAST))
            actual_rows = list(base_qs.filter(import_type=IMPORT_TYPE_ACTUAL))

            def _make_key(row):
                return (
                    row.team_id,
                    row.assignee_id if row.assignee_id is not None else f'__raw__{row.assignee_raw}',
                    row.label_id if row.label_id is not None else f'__raw__{row.label_raw}',
                    row.mapping_id if row.mapping_id is not None else f'__raw__{row.mapping_raw}',
                )

            def _row_meta(row):
                project = row.label.project if (row.label and row.label.project_id) else None
                programme = getattr(project, 'programme', None) if project else None
                return {
                    'team_id': row.team_id,
                    'team': row.team.name if row.team else '—',
                    'assignee_id': row.assignee_id,
                    'assignee': row.assignee.display_name if row.assignee else (row.assignee_raw or '—'),
                    'label_id': row.label_id,
                    'label': row.label.label if row.label else (row.label_raw or '—'),
                    'project_id': project.id if project else None,
                    'project': project.name if project else '—',
                    'programme_id': programme.id if programme else None,
                    'programme': programme.name if programme else '—',
                    'mapping_id': row.mapping_id,
                    'mapping': row.mapping.code if row.mapping else (row.mapping_raw or '—'),
                    'mapping_name': row.mapping.name if row.mapping else (row.mapping_raw or '—'),
                }

            def _agg(rows):
                totals = {}
                meta = {}
                for row in rows:
                    key = _make_key(row)
                    totals[key] = totals.get(key, Decimal('0')) + (row.days or Decimal('0'))
                    if key not in meta:
                        meta[key] = _row_meta(row)
                return totals, meta

            f_totals, f_meta = _agg(forecast_rows)
            a_totals, a_meta = _agg(actual_rows)

            all_keys = set(f_totals.keys()) | set(a_totals.keys())
            rows = []
            for key in all_keys:
                f_days = float(f_totals.get(key, Decimal('0')))
                a_days = float(a_totals.get(key, Decimal('0')))
                delta = a_days - f_days

                if f_days == 0 and a_days > 0:
                    diff_status = 'added'
                elif f_days > 0 and a_days == 0:
                    diff_status = 'removed'
                elif abs(delta) > 0.0001:
                    diff_status = 'changed'
                else:
                    diff_status = 'unchanged'

                meta = f_meta.get(key) or a_meta.get(key, {})
                rows.append({
                    **meta,
                    'forecast_days': round(f_days, 2),
                    'actual_days': round(a_days, 2),
                    'delta': round(delta, 2),
                    'status': diff_status,
                })

            rows.sort(key=lambda r: (r.get('team', ''), r.get('assignee', ''), r.get('label', '')))

            forecast_total = sum(r['forecast_days'] for r in rows)
            actual_total = sum(r['actual_days'] for r in rows)
            delta_total = actual_total - forecast_total

            summary = {
                'forecast_total_days': round(forecast_total, 2),
                'actual_total_days': round(actual_total, 2),
                'delta': round(delta_total, 2),
                'added': sum(1 for r in rows if r['status'] == 'added'),
                'removed': sum(1 for r in rows if r['status'] == 'removed'),
                'changed': sum(1 for r in rows if r['status'] == 'changed'),
                'unchanged': sum(1 for r in rows if r['status'] == 'unchanged'),
            }

            return Response({
                'forecast_complete': True,
                'actual_complete': True,
                'can_compare': True,
                'rows': rows,
                'summary': summary,
            })

        except Exception as e:
            logger.exception('Error running sprint compare: %s', e)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectActualsViewSet(viewsets.ViewSet):

    def _base_qs(self):
        return ProjectActuals.objects.select_related(
            'project', 'project__completed_sprint', 'programme', 'label',
            'assigned_team', 'last_updated_sprint',
        ).prefetch_related(
            'collaborators',
            'project__labels',
            'sprint_actuals__sprint__financial_year',
        )

    def list(self, request):
        from django.db.models import Q
        qs = self._base_qs()

        project_id = request.query_params.get('project_id')
        programme_id = request.query_params.get('programme_id')
        fy_id = request.query_params.get('fy_id')
        team_id = request.query_params.get('team_id')

        if project_id:
            qs = qs.filter(project_id=project_id)
        if programme_id:
            qs = qs.filter(programme_id=programme_id)
        if fy_id:
            qs = qs.filter(sprint_actuals__sprint__financial_year_id=fy_id).distinct()
        if team_id:
            qs = qs.filter(
                Q(assigned_team_id=team_id) | Q(collaborators__id=team_id)
            ).distinct()

        return Response(ProjectActualsSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            obj = self._base_qs().get(pk=pk)
        except ProjectActuals.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectActualsSerializer(obj).data)

    def partial_update(self, request, pk=None):
        try:
            obj = self._base_qs().get(pk=pk)
        except ProjectActuals.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        allowed = {'ignore_risk', 'ignore_risk_notes', 'ignore_previous_fy_cost'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        s = ProjectActualsSerializer(obj, data=data, partial=True)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        s.save()
        return Response(ProjectActualsSerializer(self._base_qs().get(pk=pk)).data)

    @action(detail=True, methods=['post'], url_path='mark-complete')
    def mark_complete(self, request, pk=None):
        try:
            obj = self._base_qs().get(pk=pk)
        except ProjectActuals.DoesNotExist:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        sprint_id = request.data.get('sprint_id')
        if not sprint_id:
            return Response({'error': 'sprint_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.sprints.models import Sprint
        try:
            sprint = Sprint.objects.get(pk=sprint_id)
        except Sprint.DoesNotExist:
            return Response({'error': 'Sprint not found.'}, status=status.HTTP_404_NOT_FOUND)
        project = obj.project
        project.status = project.STATUS_COMPLETED
        project.completed_sprint = sprint
        project.save(update_fields=['status', 'completed_sprint'])
        return Response(ProjectActualsSerializer(self._base_qs().get(pk=pk)).data)

    @action(detail=False, methods=['get'], url_path='fy-options')
    def fy_options(self, request):
        from apps.financial_years.models import FinancialYear
        fy_ids = ProjectSprintActual.objects.values_list(
            'sprint__financial_year_id', flat=True
        ).distinct()
        qs = FinancialYear.objects.filter(pk__in=fy_ids).order_by('-start_date').values('id', 'short_fy', 'long_fy')
        return Response(list(qs))

    @action(detail=False, methods=['get'], url_path='project-options')
    def project_options(self, request):
        qs = ProjectActuals.objects.select_related('project')
        programme_id = request.query_params.get('programme_id')
        if programme_id:
            qs = qs.filter(programme_id=programme_id)
        return Response([
            {'id': pa.project_id, 'name': pa.project.name}
            for pa in qs.order_by('project__name')
        ])

    @action(detail=False, methods=['get'], url_path='fy-sprints')
    def fy_sprints(self, request):
        from apps.sprints.models import Sprint
        fy_id = request.query_params.get('fy_id')
        if not fy_id:
            return Response([])
        sprints = (
            Sprint.objects
            .filter(financial_year_id=fy_id)
            .order_by('sprint_number')
            .values('id', 'sprint_name', 'sprint_number')
        )
        return Response(list(sprints))

    @action(detail=False, methods=['post'], url_path='copy-from-previous-fy')
    def copy_from_previous_fy(self, request):
        from apps.financial_years.models import FinancialYear
        from apps.projects.models import Project
        fy_id = request.data.get('fy_id')
        if not fy_id:
            return Response({'error': 'fy_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fy = FinancialYear.objects.get(pk=fy_id)
        except FinancialYear.DoesNotExist:
            return Response({'error': 'Financial year not found.'}, status=status.HTTP_404_NOT_FOUND)

        prev_fy = FinancialYear.objects.filter(
            start_date__lt=fy.start_date
        ).order_by('-start_date').first()

        if not prev_fy:
            return Response({'created': 0, 'existing': 0})

        prev_pa_ids = ProjectSprintActual.objects.filter(
            sprint__financial_year=prev_fy
        ).values_list('project_actuals_id', flat=True).distinct()

        project_ids = ProjectActuals.objects.filter(
            pk__in=prev_pa_ids
        ).values_list('project_id', flat=True)

        created = existing = 0
        for project in Project.objects.filter(pk__in=project_ids):
            _, was_created = ProjectActuals.objects.get_or_create(project=project)
            if was_created:
                created += 1
            else:
                existing += 1

        return Response({'created': created, 'existing': existing})

    @action(detail=False, methods=['get'], url_path='team-options')
    def team_options(self, request):
        from apps.delivery_teams.models import DeliveryTeam
        assigned_ids = set(
            ProjectActuals.objects.exclude(assigned_team=None)
            .values_list('assigned_team_id', flat=True)
        )
        collab_ids = set(
            ProjectActuals.objects.values_list('collaborators__id', flat=True)
        ) - {None}
        all_ids = assigned_ids | collab_ids
        qs = DeliveryTeam.objects.filter(pk__in=all_ids).order_by('name').values('id', 'name')
        return Response(list(qs))
