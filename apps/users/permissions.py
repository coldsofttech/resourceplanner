from rest_framework.permissions import BasePermission

# Maps API URL path segments (after /api/v1/) to Django app_labels.
# Staff users bypass all checks; non-staff need at least one permission in the app.
_API_MODULE_MAP = {
    'delivery-teams': 'delivery_teams',
    'team-members': 'team_members',
    'leaves': 'member_leaves',
    'fy': 'financial_years',
    'sprints': 'sprints',
    'sprint-capacity': 'sprints',
    'resource-plans': 'resource_plans',
    'programmes': 'programmes',
    'projects': 'projects',
    'project-views': 'projects',
    'contacts': 'contacts',
    'holidays': 'public_holidays',
    'skills': 'skills',
    'locations': 'office_locations',
    'roles': 'team_roles',
    'employment-types': 'employment_types',
    'project-types': 'project_types',
    'project-sub-statuses': 'project_sub_statuses',
    'tags': 'tags',
}


class ModulePermission(BasePermission):
    """
    Deny access to module APIs for users without any permission in that module.
    Staff users bypass all checks. Unrecognised endpoints are allowed through.
    """
    message = 'You do not have permission to access this module.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True

        path = request.path
        if path.startswith('/api/v1/'):
            tail = path[len('/api/v1/'):]
            segment = tail.split('/')[0]
            app_label = _API_MODULE_MAP.get(segment)
            if app_label:
                return request.user.has_module_perms(app_label)

        return True
