import logging

from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.core.mail.backends.console import EmailBackend as ConsoleBackend

logger = logging.getLogger(__name__)


class ConfigurationEmailBackend:
    """
    Email backend that reads SMTP settings from ConfigurationService at runtime
    instead of from settings.py, so admins can change them via the UI.
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._backend = self._build_backend(**kwargs)

    def _build_backend(self, **kwargs):
        try:
            from apps.configurations.services import ConfigurationService
            protocol = ConfigurationService.get_str('EMAIL_PROTOCOL', 'console')
            host = ConfigurationService.get_str('EMAIL_HOST', 'localhost')
            port = ConfigurationService.get_int('EMAIL_PORT', 25)
            user = ConfigurationService.get_str('EMAIL_HOST_USER', '')
            password = ConfigurationService.get_str('EMAIL_HOST_PASSWORD', '')
        except Exception:
            protocol = 'console'
            host, port, user, password = 'localhost', 25, '', ''

        if protocol == 'console':
            return ConsoleBackend(**kwargs)

        use_tls = protocol == 'smtp_tls'
        use_ssl = protocol == 'smtp_ssl'
        return SMTPBackend(
            host=host,
            port=port,
            username=user,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            **kwargs,
        )

    def open(self):
        return self._backend.open()

    def close(self):
        return self._backend.close()

    def send_messages(self, email_messages):
        return self._backend.send_messages(email_messages)

    def __enter__(self):
        self._backend.__enter__()
        return self

    def __exit__(self, *args):
        return self._backend.__exit__(*args)
