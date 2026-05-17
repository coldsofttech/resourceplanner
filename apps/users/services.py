"""
SSO service layer: OAuth2 and SAML authentication flows.
User provisioning from external identity providers.
"""

import logging
import secrets
import urllib.parse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OAuth2 / OpenID Connect
# ---------------------------------------------------------------------------

class OAuth2Service:
    """Generic OAuth2 / OIDC service driven by Configuration DB values."""

    @staticmethod
    def _cfg(key: str, fallback: str = '') -> str:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_str(key, fallback)

    @classmethod
    def build_auth_url(cls, request, state: str) -> str:
        auth_url  = cls._cfg('SSO_OAUTH2_AUTH_URL')
        client_id = cls._cfg('SSO_OAUTH2_CLIENT_ID')
        scope     = cls._cfg('SSO_OAUTH2_SCOPE', 'openid email profile')
        redirect_uri = _abs_url(request, '/sso/oauth2/callback/')

        if not auth_url or not client_id:
            raise ValueError('OAuth2 is not fully configured (missing AUTH_URL or CLIENT_ID).')

        params = urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': client_id,
            'scope': scope,
            'redirect_uri': redirect_uri,
            'state': state,
        })
        return f'{auth_url}?{params}'

    @classmethod
    def exchange_code(cls, request, code: str) -> dict:
        import requests as req
        token_url     = cls._cfg('SSO_OAUTH2_TOKEN_URL')
        client_id     = cls._cfg('SSO_OAUTH2_CLIENT_ID')
        client_secret = cls._cfg('SSO_OAUTH2_CLIENT_SECRET')
        redirect_uri  = _abs_url(request, '/sso/oauth2/callback/')

        resp = req.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
                'client_id': client_id,
                'client_secret': client_secret,
            },
            headers={'Accept': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def get_user_info(cls, access_token: str) -> dict:
        import requests as req
        userinfo_url = cls._cfg('SSO_OAUTH2_USERINFO_URL')
        if not userinfo_url:
            return {}
        resp = req.get(
            userinfo_url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def normalise_user_info(token_data: dict, user_info: dict) -> dict:
        """
        Merge token response + user-info response into a normalised dict.
        Handles field-name differences across GitHub, Azure AD, Google, Okta, etc.
        """
        merged = {**token_data, **user_info}

        uid = str(
            merged.get('sub') or merged.get('id') or merged.get('oid') or
            merged.get('login') or ''
        )
        email = (
            merged.get('email') or merged.get('upn') or
            merged.get('preferred_username') or merged.get('unique_name') or ''
        )
        name = (
            merged.get('name') or merged.get('displayName') or
            merged.get('login') or ''
        )
        first = merged.get('given_name') or merged.get('firstName') or ''
        last  = merged.get('family_name') or merged.get('lastName') or ''
        avatar = merged.get('avatar_url') or merged.get('picture') or ''

        return {
            'uid': uid or email,
            'email': email,
            'name': name,
            'first_name': first,
            'last_name': last,
            'avatar_url': avatar,
        }


# ---------------------------------------------------------------------------
# SAML 2.0
# ---------------------------------------------------------------------------

class SAMLService:
    """
    SAML 2.0 SP-initiated SSO.
    Requires python3-saml: pip install python3-saml
    """

    @staticmethod
    def _cfg(key: str, fallback: str = '') -> str:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_str(key, fallback)

    @classmethod
    def _saml_settings(cls, request) -> dict:
        sp_acs = cls._cfg('SSO_SAML_SP_ACS_URL') or _abs_url(request, '/sso/saml/acs/')
        sp_entity = cls._cfg('SSO_SAML_SP_ENTITY_ID') or _abs_url(request, '/')
        return {
            'strict': True,
            'debug': False,
            'sp': {
                'entityId': sp_entity,
                'assertionConsumerService': {
                    'url': sp_acs,
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
                },
                'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
            },
            'idp': {
                'entityId': cls._cfg('SSO_SAML_IDP_ENTITY_ID'),
                'singleSignOnService': {
                    'url': cls._cfg('SSO_SAML_IDP_SSO_URL'),
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
                },
                'x509cert': cls._cfg('SSO_SAML_IDP_CERT'),
            },
        }

    @classmethod
    def _prepare_request(cls, request) -> dict:
        return {
            'https': 'on' if request.is_secure() else 'off',
            'http_host': request.META.get('HTTP_HOST', ''),
            'script_name': request.META.get('PATH_INFO', ''),
            'get_data': request.GET.copy(),
            'post_data': request.POST.copy(),
        }

    @classmethod
    def get_auth(cls, request):
        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth
        except ImportError:
            raise RuntimeError(
                'python3-saml is not installed. '
                'Run: pip install python3-saml'
            )
        return OneLogin_Saml2_Auth(
            cls._prepare_request(request),
            custom_base_path=None,
            old_settings=cls._saml_settings(request),
        )

    @classmethod
    def get_login_url(cls, request, relay_state: str = '/') -> str:
        return cls.get_auth(request).login(return_to=relay_state)

    @classmethod
    def get_metadata(cls, request) -> bytes:
        auth = cls.get_auth(request)
        settings = auth.get_settings()
        metadata = settings.get_sp_metadata()
        errors = settings.validate_metadata(metadata)
        if errors:
            raise ValueError(', '.join(errors))
        return metadata

    @classmethod
    def process_response(cls, request) -> tuple:
        """Returns (normalised_user_info_dict, errors_list)."""
        auth = cls.get_auth(request)
        auth.process_response()
        errors = auth.get_errors()
        if errors:
            return {}, errors
        if not auth.is_authenticated():
            return {}, ['SAML authentication failed.']

        attrs  = auth.get_attributes()
        nameid = auth.get_nameid()

        def _pick(*names):
            for n in names:
                if n in attrs and attrs[n]:
                    return attrs[n][0]
            return ''

        email = _pick(
            'email', 'mail',
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
            'urn:oid:0.9.2342.19200300.100.1.3',
        ) or nameid
        first = _pick(
            'firstName', 'givenName', 'first_name',
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
        )
        last = _pick(
            'lastName', 'sn', 'last_name', 'surname',
            'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname',
        )
        name = _pick('displayName', 'cn', 'name') or f'{first} {last}'.strip()

        return {
            'uid': nameid or email,
            'email': email,
            'name': name,
            'first_name': first,
            'last_name': last,
            'avatar_url': '',
        }, []


# ---------------------------------------------------------------------------
# User provisioning
# ---------------------------------------------------------------------------

def get_or_create_sso_user(
    provider: str, uid: str, email: str, name: str = '',
    first_name: str = '', last_name: str = '', avatar_url: str = '',
):
    """
    Find or create a Django User from an SSO identity.
    Matching priority: (provider, uid) profile → email → create new.
    """
    from django.contrib.auth import get_user_model
    from .models import UserProfile

    User = get_user_model()

    # 1. Existing SSO profile?
    try:
        profile = UserProfile.objects.select_related('user').get(
            sso_provider=provider, sso_uid=uid
        )
        # Keep avatar in sync
        if avatar_url and profile.avatar_url != avatar_url:
            profile.avatar_url = avatar_url
            profile.save(update_fields=['avatar_url'])
        return profile.user
    except UserProfile.DoesNotExist:
        pass

    # 2. Existing user with matching email?
    user = User.objects.filter(email__iexact=email).first() if email else None

    # 3. Create a brand-new user
    if user is None:
        base_username = (email.split('@')[0] if email else (uid or 'sso_user')).lower()
        username = _unique_username(base_username, User)
        fn = first_name or (name.split()[0] if name else '')
        ln = last_name  or (' '.join(name.split()[1:]) if name and ' ' in name else '')
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=fn[:150],
            last_name=ln[:150],
        )
        from .utils import add_to_guest_group
        add_to_guest_group(user)

    # 4. Attach SSO profile
    UserProfile.objects.get_or_create(
        sso_provider=provider,
        sso_uid=uid,
        defaults={'user': user, 'avatar_url': avatar_url or ''},
    )
    return user


def _unique_username(base: str, User) -> str:
    username = base[:150]
    if not User.objects.filter(username=username).exists():
        return username
    for i in range(2, 99999):
        candidate = f'{base[:146]}{i}'
        if not User.objects.filter(username=candidate).exists():
            return candidate
    return f'{base[:138]}{secrets.token_hex(6)}'


def _abs_url(request, path: str) -> str:
    scheme = 'https' if request.is_secure() else 'http'
    return f'{scheme}://{request.get_host()}{path}'
