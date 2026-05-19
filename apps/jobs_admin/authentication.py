"""
Service-token authentication for the jobs API.

The token is compared against the JOB_SERVICE_TOKEN environment variable.
No database records are needed — just set the env var and use the same value
in the Authorization header when calling the endpoint.

Usage:
    Authorization: Token <value-of-JOB_SERVICE_TOKEN>
"""
import os

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JobServiceTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return None

        provided = auth_header[6:].strip()
        expected = os.environ.get('JOB_SERVICE_TOKEN', '').strip()

        if not expected:
            raise AuthenticationFailed('JOB_SERVICE_TOKEN is not configured on the server.')
        if provided != expected:
            raise AuthenticationFailed('Invalid job service token.')

        # Return a synthetic (user, token) tuple.
        # The view only requires this auth class, so user identity is not critical.
        return (_JobServiceUser(), provided)


class _JobServiceUser:
    """Minimal user-like object so DRF permission checks don't crash."""
    is_authenticated = True
    is_active = True
    is_staff = True
    pk = None

    def __str__(self):
        return 'job-service-account'
