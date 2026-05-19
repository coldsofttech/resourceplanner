#!/usr/bin/env python
"""
CLI entry point for running Resource Planner jobs locally.

Modes
-----
direct (default)
    Bootstraps Django in-process and calls the job service layer directly.
    Requires DB credentials and all Django dependencies in the environment.

    python run_job.py sprint_status

api
    Calls the job via HTTP POST to the running Django server.
    Requires JOB_API_BASE_URL and JOB_SERVICE_TOKEN environment variables.
    The server must be running and the JOB_SERVICE_TOKEN must match.

    python run_job.py sprint_status --mode api

Available jobs:
    data_retention        — Delete records older than DATA_RETENTION_YEARS
    sprint_status         — Update Sprint.is_active based on today's date
    financial_year_status — Update FinancialYear.is_active based on today's date

Windows Task Scheduler (direct mode):
    Program:   python
    Arguments: C:\\path\\to\\resourceplanner\\run_job.py data_retention
    Start in:  C:\\path\\to\\resourceplanner

Windows Task Scheduler (api mode — server must be running):
    Program:   python
    Arguments: C:\\path\\to\\resourceplanner\\run_job.py data_retention --mode api
    Start in:  C:\\path\\to\\resourceplanner
    (Set JOB_API_BASE_URL and JOB_SERVICE_TOKEN in system environment variables)
"""
import argparse
import json
import logging
import sys


def main():
    parser = argparse.ArgumentParser(description='Run a Resource Planner background job.')
    parser.add_argument('job', help='Job name: data_retention | sprint_status | financial_year_status')
    parser.add_argument('--mode', default='direct', choices=['direct', 'api'],
                        help='direct = in-process (needs DB); api = call running server via HTTP')
    parser.add_argument('--settings', default='config.settings',
                        help='Django settings module (direct mode only, default: config.settings)')
    parser.add_argument('--api-url', default=None,
                        help='Override JOB_API_BASE_URL for api mode (e.g. http://localhost:8000)')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    if args.mode == 'api':
        from jobs.http_client import run_job_via_api
        try:
            result = run_job_via_api(args.job, base_url=args.api_url)
            print(json.dumps(result, indent=2, default=str))
            sys.exit(0)
        except RuntimeError as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            logging.getLogger(__name__).exception('Job %s failed via API: %s', args.job, exc)
            sys.exit(2)

    # direct mode — bootstrap Django in-process
    from jobs._django_setup import setup
    setup(settings_module=args.settings)

    from jobs.runner import run_job
    try:
        result = run_job(args.job)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)
    except ValueError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        logging.getLogger(__name__).exception('Job %s failed: %s', args.job, exc)
        sys.exit(2)


if __name__ == '__main__':
    main()
