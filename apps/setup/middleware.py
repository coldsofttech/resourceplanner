from django.shortcuts import redirect

_BYPASS_PREFIXES = (
    '/setup/',
    '/static/',
    '/favicon',
    '/media/',
)


def _is_setup_complete():
    try:
        from apps.configurations.models import Configuration
        c = Configuration.objects.filter(code='SETUP_COMPLETE').first()
        return c is not None and c.value == 'true'
    except Exception:
        # DB not ready (pre-migration) — don't intercept
        return True


class SetupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if not any(path.startswith(p) for p in _BYPASS_PREFIXES):
            if not _is_setup_complete():
                return redirect('/setup/')
        return self.get_response(request)
