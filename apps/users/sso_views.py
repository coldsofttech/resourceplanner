import logging
import secrets

from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .services import OAuth2Service, SAMLService, get_or_create_sso_user

logger = logging.getLogger(__name__)

_STATE_SESSION_KEY = '_oauth2_state'


# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------

def oauth2_login(request):
    state = secrets.token_urlsafe(32)
    request.session[_STATE_SESSION_KEY] = state
    try:
        url = OAuth2Service.build_auth_url(request, state)
    except ValueError as exc:
        logger.error('OAuth2 misconfigured: %s', exc)
        messages.error(request, 'SSO is not fully configured. Contact your administrator.')
        return redirect('/login/')
    return redirect(url)


def oauth2_callback(request):
    error = request.GET.get('error')
    if error:
        messages.error(request, f'SSO error: {error}')
        return redirect('/login/')

    state = request.GET.get('state', '')
    expected = request.session.pop(_STATE_SESSION_KEY, None)
    if not expected or state != expected:
        messages.error(request, 'Invalid OAuth2 state. Please try again.')
        return redirect('/login/')

    code = request.GET.get('code', '')
    if not code:
        messages.error(request, 'No authorisation code received.')
        return redirect('/login/')

    try:
        token_data = OAuth2Service.exchange_code(request, code)
        access_token = token_data.get('access_token', '')
        user_info = OAuth2Service.get_user_info(access_token) if access_token else {}
        normalised = OAuth2Service.normalise_user_info(token_data, user_info)
    except Exception as exc:
        logger.exception('OAuth2 token exchange failed: %s', exc)
        messages.error(request, 'Authentication failed. Please try again.')
        return redirect('/login/')

    from apps.configurations.services import ConfigurationService
    provider = ConfigurationService.get_str('SSO_PROVIDER_NAME', 'oauth2')

    try:
        user = get_or_create_sso_user(
            provider=provider,
            uid=normalised['uid'],
            email=normalised['email'],
            name=normalised['name'],
            first_name=normalised['first_name'],
            last_name=normalised['last_name'],
            avatar_url=normalised['avatar_url'],
        )
    except Exception as exc:
        logger.exception('SSO user provisioning failed: %s', exc)
        messages.error(request, 'Could not create your account. Contact your administrator.')
        return redirect('/login/')

    login(request, user)
    next_url = request.session.pop('auth_next', None) or '/'
    return redirect(next_url)


# ---------------------------------------------------------------------------
# SAML 2.0
# ---------------------------------------------------------------------------

def saml_login(request):
    try:
        redirect_url = SAMLService.get_login_url(request, relay_state=request.session.pop('auth_next', '/'))
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect('/login/')
    except Exception as exc:
        logger.exception('SAML login initiation failed: %s', exc)
        messages.error(request, 'SSO is not available. Contact your administrator.')
        return redirect('/login/')
    return redirect(redirect_url)


@csrf_exempt
def saml_acs(request):
    """Assertion Consumer Service — receives SAML POST from IdP."""
    try:
        user_info, errors = SAMLService.process_response(request)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect('/login/')
    except Exception as exc:
        logger.exception('SAML ACS processing failed: %s', exc)
        messages.error(request, 'SAML authentication failed.')
        return redirect('/login/')

    if errors:
        logger.error('SAML errors: %s', errors)
        messages.error(request, 'SAML authentication failed: ' + '; '.join(errors))
        return redirect('/login/')

    from apps.configurations.services import ConfigurationService
    provider = ConfigurationService.get_str('SSO_PROVIDER_NAME', 'saml')

    try:
        user = get_or_create_sso_user(
            provider=provider,
            uid=user_info['uid'],
            email=user_info['email'],
            name=user_info['name'],
            first_name=user_info['first_name'],
            last_name=user_info['last_name'],
            avatar_url=user_info.get('avatar_url', ''),
        )
    except Exception as exc:
        logger.exception('SAML user provisioning failed: %s', exc)
        messages.error(request, 'Could not create your account. Contact your administrator.')
        return redirect('/login/')

    login(request, user)
    relay = request.POST.get('RelayState') or '/'
    if not relay.startswith('/'):
        relay = '/'
    return redirect(relay)


def saml_metadata(request):
    try:
        metadata = SAMLService.get_metadata(request)
    except RuntimeError as exc:
        return HttpResponse(str(exc), status=503, content_type='text/plain')
    except Exception as exc:
        logger.exception('SAML metadata generation failed: %s', exc)
        return HttpResponse('Metadata unavailable.', status=500, content_type='text/plain')
    return HttpResponse(metadata, content_type='application/xml')
