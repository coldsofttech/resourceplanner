import logging

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
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    Recharge,
    RechargeDetail,
    SprintConfirmedRow,
    SprintImport,
    SprintImportReviewComplete,
    SprintImportRow,
)
from .serializers import (
    ImportReviewSerializer,
    ProjectFinanceTypeMappingSerializer,
    ProjectFinanceTypeSerializer,
    RechargeDetailSerializer,
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
