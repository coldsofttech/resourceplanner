"""
Job runner — routes a job name to the corresponding module's run() function.

Usage:
    from jobs.runner import run_job
    result = run_job('sprint_status')
"""
import importlib
import logging

logger = logging.getLogger(__name__)

REGISTERED_JOBS = {
    'data_retention':       'jobs.data_retention',
    'sprint_status':        'jobs.sprint_status',
    'financial_year_status': 'jobs.financial_year_status',
}


def run_job(job_name: str) -> dict:
    if job_name not in REGISTERED_JOBS:
        raise ValueError(
            f'Unknown job: {job_name!r}. '
            f'Available: {", ".join(REGISTERED_JOBS)}'
        )
    module_path = REGISTERED_JOBS[job_name]
    logger.info('[runner] Starting job: %s', job_name)
    mod = importlib.import_module(module_path)
    result = mod.run()
    logger.info('[runner] Finished job: %s → %s', job_name, result)
    return result
