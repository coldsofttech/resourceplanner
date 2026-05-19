"""
HTTP client for triggering jobs via the Django REST API.

Required environment variables:
    JOB_API_BASE_URL   Base URL of the Django server, e.g. https://app.example.com
                       Defaults to http://localhost:8000 for local use.
    JOB_SERVICE_TOKEN  Service token (same value as the server's JOB_SERVICE_TOKEN setting).

Usage:
    from jobs.http_client import run_job_via_api
    result = run_job_via_api('sprint_status')
"""
import logging
import os

logger = logging.getLogger(__name__)


def run_job_via_api(job_name: str, base_url: str | None = None, token: str | None = None) -> dict:
    """
    POST /api/v1/jobs/{job_name}/run/ and return the JSON response body.

    Raises:
        ImportError  if the `requests` library is not installed.
        RuntimeError on HTTP errors or unexpected responses.
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "The 'requests' package is required for API mode. "
            "Install it with: pip install requests"
        ) from exc

    base_url = (base_url or os.environ.get('JOB_API_BASE_URL', 'http://localhost:8000')).rstrip('/')
    token = token or os.environ.get('JOB_SERVICE_TOKEN', '')

    if not token:
        raise RuntimeError(
            'JOB_SERVICE_TOKEN is not set. '
            'Set the environment variable before using API mode.'
        )

    url = f'{base_url}/api/v1/jobs/{job_name}/run/'
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json',
    }

    logger.info('[http_client] POST %s', url)
    try:
        resp = requests.post(url, headers=headers, timeout=600)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f'Cannot connect to {base_url}: {exc}') from exc

    if resp.status_code == 401:
        raise RuntimeError('Authentication failed — check JOB_SERVICE_TOKEN.')
    if resp.status_code == 404:
        raise RuntimeError(f'Job {job_name!r} not found on server (404).')
    if not resp.ok:
        raise RuntimeError(f'Job API returned HTTP {resp.status_code}: {resp.text[:200]}')

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f'Non-JSON response from job API: {resp.text[:200]}')

    if data.get('status') == 'error':
        raise RuntimeError(f'Job {job_name!r} failed on server: {data.get("error")}')

    return data
