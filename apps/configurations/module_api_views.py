import logging

from django.db import DatabaseError, transaction
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .encryption import decrypt_value
from .models import Configuration
from .services import ConfigurationService, CONFIGURATION_DEFAULTS

logger = logging.getLogger(__name__)

_MASKED = '********'


def _serialize_config(cfg: Configuration) -> dict:
    """Return a single config as a dict, masking secret values."""
    if cfg.is_secret:
        value = _MASKED if cfg.value else ''
    else:
        value = cfg.value
    return {
        'id': cfg.pk,
        'label': cfg.label,
        'value': value,
        'data_type': cfg.data_type,
        'is_secret': cfg.is_secret,
        'description': cfg.description,
    }


def _module_data(module: str) -> dict:
    """Return all configs for a module as a dict keyed by code."""
    qs = Configuration.objects.filter(module=module).order_by('code')
    return {cfg.code: _serialize_config(cfg) for cfg in qs}


def _apply_updates(module: str, data: dict) -> tuple[dict, list]:
    """
    Apply a dict of {CODE: value} updates to configs in the given module.
    Returns (updated_data_dict, errors_list).
    """
    errors = []
    codes_in_module = set(
        Configuration.objects.filter(module=module).values_list('code', flat=True)
    )

    with transaction.atomic():
        for code, value in data.items():
            code = code.strip().upper()
            if code not in codes_in_module:
                errors.append(f"'{code}' is not a valid field for this module.")
                continue
            try:
                cfg = Configuration.objects.get(code=code)
                ConfigurationService.update_configuration(cfg.pk, str(value))
            except Exception as e:
                errors.append(f"'{code}': {e}")

    return _module_data(module), errors


class _ModuleAPIView(APIView):
    """Base class for per-module GET/PATCH API endpoints."""
    module = ''

    def get(self, request):
        try:
            return Response(_module_data(self.module), status=status.HTTP_200_OK)
        except DatabaseError as e:
            logger.exception("DB error in %s GET: %s", self.module, e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in %s GET: %s", self.module, e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request):
        if not isinstance(request.data, dict):
            return Response(
                {'error': 'Request body must be a JSON object of {CODE: value} pairs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result, errors = _apply_updates(self.module, request.data)
            response_status = status.HTTP_200_OK if not errors else status.HTTP_207_MULTI_STATUS
            payload = {'data': result}
            if errors:
                payload['errors'] = errors
            return Response(payload, status=response_status)
        except DatabaseError as e:
            logger.exception("DB error in %s PATCH: %s", self.module, e)
            return Response(
                {'error': 'A database error occurred. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error in %s PATCH: %s", self.module, e)
            return Response(
                {'error': 'An unexpected error occurred. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── Integration endpoints ──────────────────────────────────────────────────────

class IntegrationAIAPIView(_ModuleAPIView):
    module = 'integration_ai'


class IntegrationEmailAPIView(_ModuleAPIView):
    module = 'integration_email'


class IntegrationSSOAPIView(_ModuleAPIView):
    module = 'integration_sso'


class IntegrationJiraAPIView(_ModuleAPIView):
    module = 'integration_jira'


# ── Security endpoints ─────────────────────────────────────────────────────────

class SecurityAPIView(_ModuleAPIView):
    module = 'security'


class SecurityPasswordPolicyAPIView(_ModuleAPIView):
    module = 'security_password'


# ── Project Approval endpoints ─────────────────────────────────────────────────

class ProjectApprovalAPIView(_ModuleAPIView):
    module = 'project_approval'


# ── Recharge Contacts endpoints ────────────────────────────────────────────────

class RechargeContactsAPIView(_ModuleAPIView):
    module = 'recharge_contacts'


# ── Database config endpoints ──────────────────────────────────────────────────

class DatabaseStatusAPIView(APIView):
    """GET /api/v1/database/status/ — return current DB config (non-sensitive)."""

    def get(self, request):
        import os
        from django.conf import settings as django_settings

        engine = os.environ.get('DB_ENGINE', 'sqlite').lower()
        db     = django_settings.DATABASES.get('default', {})

        if engine == 'postgresql':
            payload = {
                'engine':          'postgresql',
                'host':            db.get('HOST', ''),
                'port':            db.get('PORT', '5432'),
                'name':            db.get('NAME', ''),
                'user':            db.get('USER', ''),
                'password_source': os.environ.get('DB_PASSWORD_SOURCE', 'env'),
                'secret_name':     os.environ.get('DB_SECRET_NAME', '') if os.environ.get('DB_PASSWORD_SOURCE') == 'aws' else '',
            }
        else:
            payload = {
                'engine': 'sqlite',
                'path':   str(db.get('NAME', '')),
            }

        return Response(payload)


class DatabaseTestConnectionAPIView(APIView):
    """POST /api/v1/database/test-connection/ — verify DB is reachable."""

    def post(self, request):
        from django.db import connections
        try:
            conn = connections['default']
            conn.ensure_connection()
            vendor = conn.vendor          # 'sqlite', 'postgresql', etc.
            return Response({'ok': True, 'vendor': vendor})
        except Exception as exc:
            logger.warning('DB test-connection failed: %s', exc)
            return Response(
                {'ok': False, 'error': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
