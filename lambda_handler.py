"""
AWS Lambda entry point for Resource Planner background jobs.

Supports two invocation styles:
  1. Scheduled EventBridge rule — set the rule's "Constant (JSON text)" input to:
         {"job": "sprint_status"}
  2. HTTP via API Gateway — POST body:
         {"job": "data_retention"}

Environment variables required on the Lambda function:
  DJANGO_SETTINGS_MODULE  — e.g. config.settings_lambda
  DATABASE_URL            — or individual DB_* vars read by settings
  SECRET_KEY              — Django secret key
  SECRETS_SOURCE          — 'local' or 'aws'

The Lambda execution role needs:
  - Access to the RDS instance (via VPC or RDS Proxy)
  - If SECRETS_SOURCE=aws: secretsmanager:GetSecretValue on resourceplanner/* ARNs

Example EventBridge rule schedule (cron, daily at 01:00 UTC):
  cron(0 1 * * ? *)
"""
import json
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_django_ready = False


def _ensure_django():
    global _django_ready
    if _django_ready:
        return
    from jobs._django_setup import setup
    setup(settings_module=os.environ.get('DJANGO_SETTINGS_MODULE', 'config.settings'))
    _django_ready = True


def lambda_handler(event, context):
    """Main Lambda handler — routes to the requested job."""
    _ensure_django()

    # Extract job name from event (EventBridge direct or API Gateway body)
    job_name = None
    if isinstance(event, dict):
        job_name = event.get('job')
        if not job_name and 'body' in event:
            try:
                body = json.loads(event['body'] or '{}')
                job_name = body.get('job')
            except (json.JSONDecodeError, TypeError):
                pass

    if not job_name:
        msg = "Missing 'job' key in event payload."
        logger.error(msg)
        return {'statusCode': 400, 'body': json.dumps({'error': msg})}

    from jobs.runner import run_job
    try:
        result = run_job(job_name)
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str),
        }
    except ValueError as exc:
        logger.error('Unknown job: %s', exc)
        return {'statusCode': 400, 'body': json.dumps({'error': str(exc)})}
    except Exception as exc:
        logger.exception('Job %s raised an unhandled exception', job_name)
        return {'statusCode': 500, 'body': json.dumps({'error': str(exc)})}
