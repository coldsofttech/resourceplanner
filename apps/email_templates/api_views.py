import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    EmailTemplate, EmailTemplateHeader, EmailTemplateFooter,
    SCENARIO_CHOICES, TABLE_SCENARIOS,
)
from .serializers import (
    EmailTemplateSerializer,
    EmailTemplateHeaderSerializer,
    EmailTemplateFooterSerializer,
)
from .services import SCENARIO_VARIABLES, RECHARGE_TABLE_COLUMNS, SCENARIO_META

logger = logging.getLogger(__name__)


class EmailTemplateHeaderViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplateHeader.objects.all()
    serializer_class = EmailTemplateHeaderSerializer

    @action(detail=False, methods=['get'])
    def options(self, request):
        qs = EmailTemplateHeader.objects.values('id', 'name').order_by('name')
        return Response(list(qs))


class EmailTemplateFooterViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplateFooter.objects.all()
    serializer_class = EmailTemplateFooterSerializer

    @action(detail=False, methods=['get'])
    def options(self, request):
        qs = EmailTemplateFooter.objects.values('id', 'name').order_by('name')
        return Response(list(qs))


class EmailTemplateScenariosAPIView(APIView):
    """GET — list all four scenarios with their template status."""
    def get(self, request):
        templates = {t.scenario: t for t in EmailTemplate.objects.all()}
        result = []
        for scenario_code, scenario_label in SCENARIO_CHOICES:
            tmpl = templates.get(scenario_code)
            meta = SCENARIO_META.get(scenario_code, {})
            result.append({
                'scenario': scenario_code,
                'label': scenario_label,
                'description': meta.get('description', ''),
                'icon': meta.get('icon', 'bi-envelope'),
                'color': meta.get('color', 'secondary'),
                'has_template': tmpl is not None,
                'is_active': tmpl.is_active if tmpl else False,
                'subject': tmpl.subject if tmpl else '',
                'updated_at': tmpl.updated_at.isoformat() if tmpl else None,
            })
        return Response(result)


class EmailTemplateDetailAPIView(APIView):
    """GET/PUT a template for a specific scenario (keyed by scenario slug, not pk)."""
    def get(self, request, scenario):
        if scenario not in dict(SCENARIO_CHOICES):
            return Response({'error': 'Invalid scenario.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            tmpl = EmailTemplate.objects.select_related('header', 'footer').get(scenario=scenario)
            return Response(EmailTemplateSerializer(tmpl).data)
        except EmailTemplate.DoesNotExist:
            return Response({
                'scenario': scenario,
                'subject': '',
                'body': '',
                'header_id': None,
                'footer_id': None,
                'header_name': None,
                'footer_name': None,
                'table_config': {},
                'is_active': True,
            })

    def put(self, request, scenario):
        if scenario not in dict(SCENARIO_CHOICES):
            return Response({'error': 'Invalid scenario.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            tmpl = EmailTemplate.objects.get(scenario=scenario)
            serializer = EmailTemplateSerializer(tmpl, data=request.data, partial=True)
            create = False
        except EmailTemplate.DoesNotExist:
            tmpl = EmailTemplate(scenario=scenario)
            serializer = EmailTemplateSerializer(tmpl, data=request.data, partial=True)
            create = True
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED if create else status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailTemplateVariablesAPIView(APIView):
    """GET available variables (and table columns for recharge scenarios) for a scenario."""
    def get(self, request, scenario):
        if scenario not in dict(SCENARIO_CHOICES):
            return Response({'error': 'Invalid scenario.'}, status=status.HTTP_404_NOT_FOUND)
        variables = SCENARIO_VARIABLES.get(scenario, [])
        result = {'variables': variables, 'is_table_scenario': scenario in TABLE_SCENARIOS}
        if scenario in TABLE_SCENARIOS:
            result['table_columns'] = RECHARGE_TABLE_COLUMNS
        return Response(result)
