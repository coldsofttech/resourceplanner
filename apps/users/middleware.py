import time
import logging

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# URL prefixes that do not require authentication.
_EXEMPT = (
    '/login/',
    '/logout/',
    '/register/',
    '/password-reset/',
    '/profile/change-password/',
    '/sso/',
    '/static/',
    '/media/',
    '/admin/',
    '/api/v1/',   # API auth handled separately via DRF SessionAuthentication
)

# Additional exemptions for the force-change-password flow so the user
# can reach the change-password page and log out but nothing else.
_FORCE_CHANGE_EXEMPT = (
    '/profile/change-password/',
    '/logout/',
    '/static/',
    '/media/',
)


class AuthRequiredMiddleware(MiddlewareMixin):
    """Redirect unauthenticated requests to the login page (classic) or SSO (sso mode)."""

    def process_request(self, request):
        if any(request.path.startswith(p) for p in _EXEMPT):
            return None

        if request.user.is_authenticated:
            return None

        from apps.configurations.services import ConfigurationService

        auth_mode = ConfigurationService.get_str('AUTH_MODE', 'classic')

        if auth_mode == 'sso':
            request.session['auth_next'] = request.get_full_path()
            protocol = ConfigurationService.get_str('SSO_PROTOCOL', 'oauth2')
            return redirect('/sso/saml/login/' if protocol == 'saml' else '/sso/oauth2/login/')

        next_url = request.get_full_path()
        return redirect(f'/login/?next={next_url}')


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    """
    Redirect authenticated users who must change their password.
    Triggers on must_change_password=True or when password rotation period has elapsed.
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        if any(request.path.startswith(p) for p in _FORCE_CHANGE_EXEMPT):
            return None

        try:
            profile = request.user.profile
        except Exception:
            return None

        if profile.must_change_password:
            return redirect('/profile/change-password/')

        # Password rotation check
        try:
            from apps.configurations.services import ConfigurationService
            rotation_days = ConfigurationService.get_int('PASSWORD_ROTATION_DAYS', 90)
            if rotation_days > 0 and profile.password_last_changed:
                from django.utils import timezone
                age_days = (timezone.now() - profile.password_last_changed).days
                if age_days >= rotation_days:
                    profile.must_change_password = True
                    profile.save(update_fields=['must_change_password'])
                    return redirect('/profile/change-password/')
        except Exception:
            pass

        return None


# Maps page URL prefixes to their Django app_label for module permission enforcement.
_PAGE_MODULE_MAP = {
    '/delivery-teams/': 'delivery_teams',
    '/team-members/': 'team_members',
    '/leaves/': 'member_leaves',
    '/fy/': 'financial_years',
    '/sprints/': 'sprints',
    '/resource-plan/': 'resource_plans',
    '/resource-plans/': 'resource_plans',
    '/programmes/': 'programmes',
    '/projects/': 'projects',
    '/contacts/': 'contacts',
    '/holidays/': 'public_holidays',
    '/skills/': 'skills',
    '/locations/': 'office_locations',
    '/roles/': 'team_roles',
    '/employment-types/': 'employment_types',
    '/project-types/': 'project_types',
    '/project-sub-statuses/': 'project_sub_statuses',
}


class ModulePermissionMiddleware(MiddlewareMixin):
    """
    Deny access to module pages for authenticated non-staff users who lack
    any permission in that module (deny-by-default enforcement).
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        if request.user.is_staff:
            return None

        path = request.path
        app_label = None
        for prefix, label in _PAGE_MODULE_MAP.items():
            if path.startswith(prefix):
                app_label = label
                break

        if app_label is None:
            return None

        if not request.user.has_module_perms(app_label):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied


class SessionTimeoutMiddleware(MiddlewareMixin):
    """Expire idle sessions based on the SESSION_TIMEOUT_MINUTES configuration."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        last = request.session.get('_rp_last_activity')
        if last is not None:
            from apps.configurations.services import ConfigurationService
            timeout_secs = ConfigurationService.get_int('SESSION_TIMEOUT_MINUTES', 480) * 60
            if (time.time() - last) > timeout_secs:
                logout(request)
                return redirect('/login/?reason=timeout')

        request.session['_rp_last_activity'] = time.time()
        return None
