from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

MODULE_LABELS = {
    'delivery_teams': 'Delivery Teams',
    'team_members': 'Team Members',
    'member_leaves': 'Member Leaves',
    'financial_years': 'Financial Years',
    'sprints': 'Sprints',
    'sprint_capacity': 'Sprint Capacity',
    'resource_plans': 'Resource Plans',
    'projects': 'Projects',
    'programmes': 'Programmes',
    'contacts': 'Contacts',
    'skills': 'Skills',
    'team_roles': 'Team Roles',
    'office_locations': 'Office Locations',
    'employment_types': 'Employment Types',
    'project_types': 'Project Types',
    'project_sub_statuses': 'Project Sub-Statuses',
    'public_holidays': 'Public Holidays',
}

INCLUDED_APPS = list(MODULE_LABELS.keys())


class PermissionListView(APIView):
    """Returns all permissions grouped by application module."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.contrib.auth.models import Permission

        perms_by_app = {}
        for perm in (
            Permission.objects
            .filter(content_type__app_label__in=INCLUDED_APPS)
            .select_related('content_type')
            .order_by('content_type__app_label', 'codename')
        ):
            app_label = perm.content_type.app_label
            if app_label not in perms_by_app:
                perms_by_app[app_label] = []
            perms_by_app[app_label].append({
                'id': perm.id,
                'codename': perm.codename,
                'name': perm.name,
            })

        result = []
        for app_label in INCLUDED_APPS:
            perms = perms_by_app.get(app_label, [])
            if perms:
                result.append({
                    'app_label': app_label,
                    'label': MODULE_LABELS.get(app_label, app_label.replace('_', ' ').title()),
                    'permissions': perms,
                })

        return Response(result)
