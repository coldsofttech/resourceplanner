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

        # Lazy import to avoid circular dependency at startup
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
    If the authenticated user's profile has must_change_password=True,
    redirect every request to the password-change page until they comply.
    """

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        # Allow these paths unconditionally
        if any(request.path.startswith(p) for p in _FORCE_CHANGE_EXEMPT):
            return None

        try:
            must_change = request.user.profile.must_change_password
        except Exception:
            return None

        if must_change:
            return redirect('/profile/change-password/')

        return None


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
