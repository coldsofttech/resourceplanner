"""
Generic rotating-log-handler utility.

Usage — in any module that wants a dedicated rotating log file:

    from apps.core.logging_utils import get_rotating_handler
    import logging

    logger = logging.getLogger(__name__)
    logger.addHandler(get_rotating_handler('delivery_teams'))

Or configure via settings.LOGGING (preferred for Django apps).
To add a new module simply add its logger name and a handler reference
in settings.LOGGING['loggers'] pointing at the rotating handler in
settings.LOGGING['handlers'].

Example settings block (already included for delivery_teams):

    LOGGING = {
        'handlers': {
            'delivery_teams_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': BASE_DIR / 'logs' / 'delivery_teams.log',
                'maxBytes': 10 * 1024 * 1024,
                'backupCount': 5,
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'apps.delivery_teams': {
                'handlers': ['console', 'delivery_teams_file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_rotating_handler(
    log_name: str,
    log_dir: str | Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    level: int = logging.INFO,
    fmt: str = '%(asctime)s [%(levelname)s] %(name)s — %(message)s',
) -> RotatingFileHandler:
    """
    Return a configured RotatingFileHandler for *log_name*.

    *log_dir* defaults to BASE_DIR/logs (resolved from Django settings if available,
    falling back to the current working directory).
    """
    if log_dir is None:
        try:
            from django.conf import settings as django_settings
            log_dir = getattr(django_settings, 'LOG_DIR', None) or Path(
                getattr(django_settings, 'BASE_DIR', '.') ) / 'logs'
        except Exception:
            log_dir = Path('.') / 'logs'

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=log_dir / f'{log_name}.log',
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S'))
    return handler
