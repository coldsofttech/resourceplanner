import json

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


def _setup_complete():
    try:
        from apps.configurations.models import Configuration
        c = Configuration.objects.filter(code='SETUP_COMPLETE').first()
        return c is not None and c.value == 'true'
    except Exception:
        return True


def _cfg_set(code, value):
    from apps.configurations.models import Configuration
    Configuration.objects.filter(code=code).update(value=value)


class SetupWizardView(View):
    def get(self, request):
        if _setup_complete():
            return redirect('/')
        return render(request, 'setup/wizard.html')


@method_decorator(csrf_exempt, name='dispatch')
class SetupStepView(View):
    def post(self, request):
        try:
            data    = json.loads(request.body)
            step    = data.get('step')
            payload = data.get('data', {})
        except Exception:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        handlers = {
            1: self._step_admin,
            2: self._step_app,
            3: self._step_auth,
            4: self._step_storage,
            5: self._step_integrations,
            6: self._step_complete,
        }
        handler = handlers.get(step)
        if not handler:
            return JsonResponse({'error': 'Invalid step.'}, status=400)
        return handler(payload)

    # ── Step 1: Admin account ─────────────────────────────────────────────────

    def _step_admin(self, data):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            return JsonResponse({'success': True, 'skipped': True})

        email      = (data.get('email') or '').strip()
        password   = data.get('password', '')
        confirm    = data.get('confirm', '')
        first_name = (data.get('first_name') or '').strip()
        last_name  = (data.get('last_name') or '').strip()

        errors = {}
        if not email:
            errors['email'] = 'Email is required.'
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'
        elif password != confirm:
            errors['confirm'] = 'Passwords do not match.'
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        try:
            user = User.objects.create_superuser(
                username=email[:150],
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            from apps.users.models import UserProfile
            UserProfile.objects.get_or_create(user=user)
        except Exception as exc:
            return JsonResponse({'errors': {'email': str(exc)}}, status=400)

        return JsonResponse({'success': True})

    # ── Step 2: Application settings ─────────────────────────────────────────

    def _step_app(self, data):
        app_name = (data.get('app_name') or '').strip()
        base_url = (data.get('base_url') or '').strip()
        if app_name:
            _cfg_set('APP_NAME', app_name)
        if base_url:
            _cfg_set('BASE_URL', base_url.rstrip('/'))
        return JsonResponse({'success': True})

    # ── Step 3: Authentication mode ───────────────────────────────────────────

    def _step_auth(self, data):
        auth_mode = data.get('auth_mode', 'classic')
        if auth_mode in ('classic', 'sso'):
            _cfg_set('AUTH_MODE', auth_mode)
        allow_reg = data.get('allow_registration', 'false')
        _cfg_set('ALLOW_REGISTRATION', str(allow_reg).lower())
        return JsonResponse({'success': True})

    # ── Step 4: Storage ───────────────────────────────────────────────────────

    def _step_storage(self, data):
        storage = data.get('avatar_storage', 'database')
        if storage in ('database', 'local', 's3'):
            _cfg_set('AVATAR_STORAGE', storage)
        local_path = (data.get('local_path') or '').strip()
        s3_arn     = (data.get('s3_arn') or '').strip()
        if local_path:
            _cfg_set('AVATAR_LOCAL_PATH', local_path)
        if s3_arn:
            _cfg_set('AVATAR_S3_BUCKET_ARN', s3_arn)
        return JsonResponse({'success': True})

    # ── Step 5: Optional integrations ────────────────────────────────────────

    def _step_integrations(self, data):
        email_host = (data.get('email_host') or '').strip()
        email_port = (data.get('email_port') or '').strip()
        email_user = (data.get('email_user') or '').strip()
        email_from = (data.get('email_from') or '').strip()

        if email_host:
            _cfg_set('EMAIL_PROTOCOL', 'smtp_tls')
            _cfg_set('EMAIL_HOST', email_host)
        if email_port:
            _cfg_set('EMAIL_PORT', email_port)
        if email_user:
            _cfg_set('EMAIL_HOST_USER', email_user)
        if email_from:
            _cfg_set('EMAIL_FROM', email_from)
        return JsonResponse({'success': True})

    # ── Step 6: Mark complete ─────────────────────────────────────────────────

    def _step_complete(self, data):
        from apps.configurations.models import Configuration
        Configuration.objects.update_or_create(
            code='SETUP_COMPLETE',
            defaults={
                'label': 'Setup Complete',
                'value': 'true',
                'data_type': 'boolean',
                'is_secret': False,
                'module': 'general',
                'description': 'Marks whether the initial setup wizard has been completed.',
            },
        )
        return JsonResponse({'success': True, 'redirect': '/login/'})
