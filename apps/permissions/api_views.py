import logging

from django.contrib.auth.models import Permission
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from .models import PermissionCategory

logger = logging.getLogger(__name__)

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


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _serialize_category(cat):
    return {
        'id': cat.id,
        'module': cat.module,
        'module_label': MODULE_LABELS.get(cat.module, '') if cat.module else '',
        'name': cat.name,
        'description': cat.description,
        'permission_ids': list(cat.permissions.values_list('id', flat=True)),
        'permission_count': cat.permissions.count(),
        'created_at': cat.created_at.isoformat(),
        'updated_at': cat.updated_at.isoformat(),
    }


class PermissionListView(APIView):
    """Returns all permissions grouped by application module."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
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


class PermissionCategoryViewSet(ViewSet):
    """CRUD for PermissionCategory — admin only for write operations."""
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        return None

    def list(self, request):
        cats = PermissionCategory.objects.prefetch_related('permissions').all()
        return Response([_serialize_category(c) for c in cats])

    def create(self, request):
        deny = self._require_admin(request)
        if deny:
            return deny

        name = str(request.data.get('name', '')).strip()
        if not name:
            return _err('name is required.')
        if PermissionCategory.objects.filter(name__iexact=name).exists():
            return _err('A category with this name already exists.')

        description = str(request.data.get('description', '')).strip()
        module = str(request.data.get('module', '')).strip()
        from .models import MODULE_CHOICES
        valid_modules = {m[0] for m in MODULE_CHOICES}
        if module and module not in valid_modules:
            return _err('Invalid module value.')
        perm_ids = request.data.get('permission_ids', [])
        if not isinstance(perm_ids, list):
            return _err('permission_ids must be a list.')

        try:
            cat = PermissionCategory.objects.create(name=name, description=description, module=module)
            if perm_ids:
                cat.permissions.set(Permission.objects.filter(id__in=perm_ids))
        except Exception as exc:
            logger.exception('PermissionCategory create failed: %s', exc)
            return _err('Could not create category.', status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(_serialize_category(cat), status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            cat = PermissionCategory.objects.prefetch_related('permissions').get(pk=pk)
        except PermissionCategory.DoesNotExist:
            return _err('Category not found.', status.HTTP_404_NOT_FOUND)
        return Response(_serialize_category(cat))

    def partial_update(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny

        try:
            cat = PermissionCategory.objects.prefetch_related('permissions').get(pk=pk)
        except PermissionCategory.DoesNotExist:
            return _err('Category not found.', status.HTTP_404_NOT_FOUND)

        if 'name' in request.data:
            name = str(request.data['name']).strip()
            if not name:
                return _err('name cannot be blank.')
            if PermissionCategory.objects.filter(name__iexact=name).exclude(pk=pk).exists():
                return _err('A category with this name already exists.')
            cat.name = name

        if 'description' in request.data:
            cat.description = str(request.data.get('description', '')).strip()

        if 'module' in request.data:
            from .models import MODULE_CHOICES
            module = str(request.data['module']).strip()
            valid_modules = {m[0] for m in MODULE_CHOICES}
            if module and module not in valid_modules:
                return _err('Invalid module value.')
            cat.module = module

        cat.save()

        if 'permission_ids' in request.data:
            perm_ids = request.data['permission_ids']
            if not isinstance(perm_ids, list):
                return _err('permission_ids must be a list.')
            cat.permissions.set(Permission.objects.filter(id__in=perm_ids))
            # Re-sync permissions for all groups using this category
            _sync_category_to_groups(cat)

        cat.refresh_from_db()
        return Response(_serialize_category(cat))

    def destroy(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny

        try:
            cat = PermissionCategory.objects.get(pk=pk)
        except PermissionCategory.DoesNotExist:
            return _err('Category not found.', status.HTTP_404_NOT_FOUND)

        cat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _sync_category_to_groups(category):
    """After a category's permissions change, recompute permissions for all groups using it."""
    from apps.users.models import GroupProfile
    from apps.users.serializers import _is_admin_by_coverage
    for profile in GroupProfile.objects.filter(permission_categories=category).select_related('group'):
        if profile.is_system:
            continue
        group = profile.group
        all_perm_ids = set()
        for cat in profile.permission_categories.prefetch_related('permissions').all():
            all_perm_ids.update(cat.permissions.values_list('id', flat=True))
        group.permissions.set(Permission.objects.filter(id__in=all_perm_ids))
        # Re-evaluate admin status
        new_is_admin = _is_admin_by_coverage(group)
        if profile.is_admin_group != new_is_admin:
            profile.is_admin_group = new_is_admin
            profile.save(update_fields=['is_admin_group'])
        # Sync staff flag for members
        for user in group.user_set.all():
            from apps.users.api_views import _sync_staff_for_user
            _sync_staff_for_user(user)
