import logging
import re
import sys

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

logger = logging.getLogger(__name__)


def _html_to_text(html):
    """Convert HTML email to readable plain text for console output."""
    # Remove non-content blocks entirely
    html = re.sub(r'<head[^>]*>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Headings get a blank line before and a newline after
    html = re.sub(r'<h[1-6][^>]*>', '\n\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</h[1-6]>', '\n', html, flags=re.IGNORECASE)

    # Paragraphs and divs: only the OPENING tag inserts a newline;
    # the closing tag is left for the generic stripper (avoids double-spacing).
    html = re.sub(r'<(?:p|div)[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)

    # Table rows → newline; cells → pipe separator
    html = re.sub(r'<tr[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<t[dh][^>]*>', ' │ ', html, flags=re.IGNORECASE)

    # Bold/strong → uppercase (inline, no extra newlines).
    # Use \b after tag name so <b> matches but <body>/<blockquote> do not.
    html = re.sub(
        r'<(?:strong|b)\b[^>]*>(.*?)</(?:strong|b)>',
        lambda m: m.group(1).upper(),
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip every remaining tag (closing divs/tds/tables/spans/etc.)
    html = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    html = (html
            .replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            .replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#x27;', "'")
            .replace('&#163;', '£').replace('&#183;', '·'))
    html = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), html)
    html = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), html)

    # Collapse horizontal whitespace
    html = re.sub(r'[ \t]+', ' ', html)

    # Line-by-line cleanup:
    #  • Strip leading/trailing │ and spaces from each line (layout cell noise)
    #  • Drop lines whose entire content is │ and whitespace (empty layout rows)
    #  • Collapse runs of consecutive blank lines to a single blank
    cleaned: list[str] = []
    prev_blank = False
    for raw in html.splitlines():
        ln = re.sub(r'^[ │\t]+|[ │\t]+$', '', raw)
        if not ln:
            if not prev_blank:
                cleaned.append('')
            prev_blank = True
        else:
            cleaned.append(ln)
            prev_blank = False

    return '\n'.join(cleaned).strip()


class PrettyConsoleBackend(BaseEmailBackend):
    """Console email backend — prints messages in a readable, formatted style."""

    def send_messages(self, email_messages):
        msgs = list(email_messages)
        for msg in msgs:
            self._print_message(msg)
        return len(msgs)

    def _print_message(self, msg):
        RESET  = '\033[0m'
        BOLD   = '\033[1m'
        DIM    = '\033[2m'
        BLUE   = '\033[94m'
        CYAN   = '\033[96m'
        YELLOW = '\033[93m'
        BG_BLU = '\033[44m'
        WHITE  = '\033[97m'
        SEP    = '─' * 72
        THICK  = '═' * 72

        out = sys.stderr
        out.write(f'\n{BOLD}{BLUE}{THICK}{RESET}\n')
        out.write(f'{BOLD}{BG_BLU}{WHITE}  ✉  OUTGOING EMAIL  (console mode — not actually sent)  {RESET}\n')
        out.write(f'{BOLD}{BLUE}{THICK}{RESET}\n')
        out.write(f'  {BOLD}To     :{RESET} {CYAN}{", ".join(msg.to) or "(none)"}{RESET}\n')
        if getattr(msg, 'cc', None):
            out.write(f'  {BOLD}Cc     :{RESET} {", ".join(msg.cc)}\n')
        out.write(f'  {BOLD}From   :{RESET} {msg.from_email or "(default)"}\n')
        out.write(f'  {BOLD}Subject:{RESET} {YELLOW}{msg.subject}{RESET}\n')
        out.write(f'{DIM}{SEP}{RESET}\n')
        body = msg.body or ''
        if getattr(msg, 'content_subtype', None) == 'html' or '<html' in body[:400].lower():
            body = _html_to_text(body)
        for line in body.splitlines():
            out.write(f'  {line}\n')
        out.write(f'{BOLD}{BLUE}{THICK}{RESET}\n\n')
        out.flush()


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
            return PrettyConsoleBackend(**kwargs)

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
