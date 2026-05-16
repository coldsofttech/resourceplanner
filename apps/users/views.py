import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm, AdminUserCreateForm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classic auth
# ---------------------------------------------------------------------------

def login_view(request):
    from apps.configurations.services import ConfigurationService
    if ConfigurationService.get_str('AUTH_MODE', 'classic') == 'sso':
        protocol = ConfigurationService.get_str('SSO_PROTOCOL', 'oauth2')
        return redirect('/sso/saml/login/' if protocol == 'saml' else '/sso/oauth2/login/')

    if request.user.is_authenticated:
        return redirect(request.GET.get('next') or '/')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['email'],
            password=form.cleaned_data['password'],
        )
        if user is not None:
            login(request, user)
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            return redirect(request.POST.get('next') or request.GET.get('next') or '/')
        form.add_error(None, 'Invalid email or password.')

    return render(request, 'users/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


def register_view(request):
    from apps.configurations.services import ConfigurationService
    if ConfigurationService.get_str('AUTH_MODE', 'classic') == 'sso':
        return redirect('/')

    allow = ConfigurationService.get_bool('ALLOW_REGISTRATION', True)
    if not allow:
        messages.error(request, 'Self-registration is currently disabled.')
        return redirect('/login/')

    if request.user.is_authenticated:
        return redirect('/')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='apps.users.backends.EmailBackend')
        # Assign to GUEST group by default
        try:
            from django.contrib.auth.models import Group
            from apps.users.apps import GUEST_GROUP_NAME
            guest_group = Group.objects.get(name=GUEST_GROUP_NAME)
            guest_group.user_set.add(user)
        except Exception:
            pass
        messages.success(request, f'Welcome, {user.first_name or user.email}!')
        return redirect('/')

    return render(request, 'users/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/login/')


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    from apps.users.apps import DEFAULT_ADMIN_EMAIL
    user = request.user
    is_default_admin = user.email.lower() == DEFAULT_ADMIN_EMAIL.lower()

    profile_form = ProfileForm(initial={
        'first_name': user.first_name,
        'last_name': user.last_name,
    }, user=user)
    password_form = ChangePasswordForm(user=user)

    if is_default_admin:
        _ro = {'readonly': True, 'style': 'cursor:not-allowed;background:var(--rp-surface-muted,#f8f9fa)'}
        profile_form.fields['first_name'].widget.attrs.update(_ro)
        profile_form.fields['last_name'].widget.attrs.update(_ro)

    try:
        profile = user.profile
        sso_provider = profile.sso_provider
        password_last_changed = profile.password_last_changed
        user_timezone = profile.timezone or 'UTC'
        user_theme = profile.theme or 'light'
    except Exception:
        sso_provider = ''
        password_last_changed = None
        user_timezone = 'UTC'
        user_theme = 'light'

    is_sso = bool(sso_provider)
    user_groups = list(user.groups.select_related('profile').all())

    # Common timezone list for selector
    try:
        import zoneinfo
        all_timezones = sorted(zoneinfo.available_timezones())
    except Exception:
        all_timezones = ['UTC', 'Europe/London', 'Europe/Paris', 'US/Eastern', 'US/Pacific', 'Asia/Kolkata', 'Asia/Tokyo', 'Australia/Sydney']

    return render(request, 'users/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'is_sso': is_sso,
        'sso_provider': sso_provider,
        'is_default_admin': is_default_admin,
        'user_groups': user_groups,
        'password_last_changed': password_last_changed,
        'user_timezone': user_timezone,
        'user_theme': user_theme,
        'all_timezones': all_timezones,
    })


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard_view(request):
    return render(request, 'dashboard/dashboard.html')


def privacy_view(request):
    return render(request, 'users/privacy.html')


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

def user_list_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/user_list.html')


def user_create_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')

    form = AdminUserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # Send invitation email (best-effort)
        try:
            from .api_views import _send_invitation_email
            _send_invitation_email(user, request)
        except Exception as exc:
            logger.warning('Invitation email failed for %s: %s', user.email, exc)
        messages.success(request, f'User {user.email} created. An invitation email has been sent.')
        return redirect('/users/')

    return render(request, 'users/user_form.html', {
        'form': form,
        'page_title': 'Create User',
        'submit_label': 'Create user',
    })


def user_detail_view(request, pk):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/user_detail.html', {'target_user_pk': pk})


# ---------------------------------------------------------------------------
# Force password change (first login / rotation)
# ---------------------------------------------------------------------------

@login_required
def force_change_password_view(request):
    user = request.user
    try:
        profile = user.profile
    except Exception:
        return redirect('/')

    if not profile.must_change_password:
        return redirect('/')

    error = None
    if request.method == 'POST':
        new_pwd = request.POST.get('new_password1', '')
        confirm = request.POST.get('new_password2', '')

        if new_pwd != confirm:
            error = 'Passwords do not match.'
        else:
            try:
                validate_password(new_pwd, user=user)
                user.set_password(new_pwd)
                user.save()

                from django.utils import timezone
                profile.must_change_password = False
                profile.password_last_changed = timezone.now()
                profile.save(update_fields=['must_change_password', 'password_last_changed'])

                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Password updated. Welcome!')
                return redirect('/')
            except DjangoValidationError as exc:
                error = ' '.join(exc.messages)

    return render(request, 'users/force_change_password.html', {'error': error})


# ---------------------------------------------------------------------------
# User Groups management
# ---------------------------------------------------------------------------

def group_list_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/group_list.html')


def group_create_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/group_form.html', {
        'page_title': 'Create Group',
        'submit_label': 'Create group',
        'back_url': '/user-groups/',
    })


def group_detail_view(request, pk):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/group_detail.html', {'group_pk': pk})


def group_edit_view(request, pk):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'users/group_form.html', {
        'page_title': 'Edit Group',
        'submit_label': 'Save changes',
        'back_url': f'/user-groups/{pk}/',
        'group_pk': pk,
    })


# ---------------------------------------------------------------------------
# Password reset — thin wrappers around Django built-ins
# ---------------------------------------------------------------------------

class RpPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.txt'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def get_from_email(self):
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_str('EMAIL_FROM', '') or super().get_from_email()
        except Exception:
            return super().get_from_email()


class RpPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'


class RpPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Clear must_change_password and record password_last_changed after reset
        try:
            user = form.user
            from django.utils import timezone
            profile, _ = user.profile.__class__.objects.get_or_create(user=user)
            profile.must_change_password = False
            profile.password_last_changed = timezone.now()
            profile.save(update_fields=['must_change_password', 'password_last_changed'])
        except Exception:
            pass
        return response


class RpPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'
