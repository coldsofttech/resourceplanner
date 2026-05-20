import logging

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrgChartNode
from .serializers import OrgChartNodeSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class OrgChartNodeListCreateView(APIView):
    """GET /api/v1/orgchart/nodes/   POST /api/v1/orgchart/nodes/"""

    def get(self, request):
        nodes = OrgChartNode.objects.select_related('team', 'parent', 'team_member').all()
        return Response(OrgChartNodeSerializer(nodes, many=True).data)

    def post(self, request):
        data = request.data
        if not data.get('name', '').strip():
            return Response({'name': 'Required.'}, status=status.HTTP_400_BAD_REQUEST)

        parent = None
        if data.get('parent'):
            try:
                parent = OrgChartNode.objects.get(pk=data['parent'])
            except OrgChartNode.DoesNotExist:
                return Response({'parent': 'Parent node not found.'}, status=status.HTTP_400_BAD_REQUEST)

        team = None
        if data.get('team'):
            from apps.delivery_teams.models import DeliveryTeam
            try:
                team = DeliveryTeam.objects.get(pk=data['team'])
            except DeliveryTeam.DoesNotExist:
                return Response({'team': 'Team not found.'}, status=status.HTTP_400_BAD_REQUEST)

        team_member = None
        if data.get('team_member'):
            from apps.team_members.models import TeamMember
            try:
                team_member = TeamMember.objects.get(pk=data['team_member'])
            except TeamMember.DoesNotExist:
                return Response({'team_member': 'Team member not found.'}, status=status.HTTP_400_BAD_REQUEST)

        node = OrgChartNode.objects.create(
            node_type=data.get('node_type', OrgChartNode.TYPE_MEMBER),
            name=data['name'].strip(),
            job_title=data.get('job_title', ''),
            email=data.get('email', ''),
            avatar_url=data.get('avatar_url', ''),
            team=team,
            parent=parent,
            team_member=team_member,
            is_vacant=bool(data.get('is_vacant', False)),
            sort_order=int(data.get('sort_order', 0)),
            created_by=request.user,
        )
        return Response(OrgChartNodeSerializer(node).data, status=status.HTTP_201_CREATED)


class OrgChartNodeDetailView(APIView):
    """GET / PATCH / DELETE /api/v1/orgchart/nodes/<pk>/"""

    def _get(self, pk):
        try:
            return OrgChartNode.objects.select_related('team', 'parent', 'team_member').get(pk=pk)
        except OrgChartNode.DoesNotExist:
            return None

    def get(self, request, pk):
        node = self._get(pk)
        if not node:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrgChartNodeSerializer(node).data)

    def patch(self, request, pk):
        node = self._get(pk)
        if not node:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        if 'node_type' in data:
            node.node_type = data['node_type']
        if 'name' in data:
            node.name = data['name'].strip() or node.name
        for field in ['job_title', 'email', 'avatar_url', 'is_vacant', 'sort_order']:
            if field in data:
                setattr(node, field, data[field])

        if 'parent' in data:
            if data['parent']:
                try:
                    node.parent = OrgChartNode.objects.get(pk=data['parent'])
                except OrgChartNode.DoesNotExist:
                    return Response({'parent': 'Not found.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                node.parent = None

        if 'team' in data:
            if data['team']:
                from apps.delivery_teams.models import DeliveryTeam
                try:
                    node.team = DeliveryTeam.objects.get(pk=data['team'])
                except DeliveryTeam.DoesNotExist:
                    return Response({'team': 'Not found.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                node.team = None

        if 'team_member' in data:
            if data['team_member']:
                from apps.team_members.models import TeamMember
                try:
                    tm = TeamMember.objects.get(pk=data['team_member'])
                    node.team_member = tm
                    # Auto-fill name/email from team member if node fields are empty
                    if not node.name:
                        node.name = tm.display_name
                    if not node.email:
                        node.email = tm.email_address
                    if not node.job_title:
                        node.job_title = tm.role.name if tm.role else ''
                except TeamMember.DoesNotExist:
                    return Response({'team_member': 'Not found.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                node.team_member = None

        node.save()
        return Response(OrgChartNodeSerializer(node).data)

    def delete(self, request, pk):
        node = self._get(pk)
        if not node:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Re-parent children to grandparent (prevent orphaned nodes)
        OrgChartNode.objects.filter(parent=node).update(parent=node.parent)
        node.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrgChartImportView(APIView):
    """POST /api/v1/orgchart/import/  — seed nodes from active TeamMembers."""

    def post(self, request):
        from apps.team_members.models import TeamMember, TeamMemberAssignment

        clear = request.data.get('clear_existing', False)
        if clear:
            OrgChartNode.objects.all().delete()

        members = TeamMember.objects.filter(is_active=True).select_related(
            'role',
        ).prefetch_related('team_assignments__team')

        created = 0
        for tm in members:
            # Skip if already linked
            if OrgChartNode.objects.filter(team_member=tm).exists():
                continue

            team = tm.team  # first assigned team or None

            OrgChartNode.objects.create(
                name=tm.display_name,
                job_title=tm.role.name if tm.role else '',
                email=tm.email_address,
                team=team,
                team_member=tm,
                is_vacant=False,
                created_by=request.user,
            )
            created += 1

        return Response({'created': created, 'message': f'Imported {created} team member(s).'})


class OrgChartTeamsView(APIView):
    """GET /api/v1/orgchart/teams/ — team options for node assignment."""

    def get(self, request):
        from apps.delivery_teams.models import DeliveryTeam
        teams = DeliveryTeam.objects.filter(is_active=True).values('id', 'name')
        return Response(list(teams))


class OrgChartMembersView(APIView):
    """GET /api/v1/orgchart/members/ — team member options."""

    def get(self, request):
        from apps.team_members.models import TeamMember
        members = TeamMember.objects.filter(is_active=True).values(
            'id', 'display_name', 'email_address',
        )
        return Response(list(members))
