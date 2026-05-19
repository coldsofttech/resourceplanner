import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .authentication import JobServiceTokenAuthentication

logger = logging.getLogger(__name__)

REGISTERED_JOBS = {
    'data_retention',
    'sprint_status',
    'financial_year_status',
}


class JobRunView(APIView):
    """
    POST /api/v1/jobs/{job_name}/run/

    Requires:  Authorization: Token <JOB_SERVICE_TOKEN>

    Runs the named background job synchronously and returns its result dict.
    Only accepts the job-service token — session/browser auth is deliberately excluded.
    """
    authentication_classes = [JobServiceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, job_name):
        if job_name not in REGISTERED_JOBS:
            return Response(
                {'error': f'Unknown job: {job_name!r}. Valid jobs: {sorted(REGISTERED_JOBS)}'},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info('[jobs_admin] Running job %r via API', job_name)
        try:
            import importlib
            mod = importlib.import_module(f'jobs.{job_name}')
            result = mod.run()
            logger.info('[jobs_admin] Job %r completed: %s', job_name, result)
            return Response({'job': job_name, 'status': 'ok', 'result': result})
        except Exception as exc:
            logger.exception('[jobs_admin] Job %r failed: %s', job_name, exc)
            return Response(
                {'job': job_name, 'status': 'error', 'error': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
