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
        login(request, user)
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
    user = request.user
    profile_form = ProfileForm(initial={
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
    }, user=user)
    password_form = ChangePasswordForm(user=user)

    try:
        sso_provider = user.profile.sso_provider
    except Exception:
        sso_provider = ''

    is_sso = bool(sso_provider)

    return render(request, 'users/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'is_sso': is_sso,
        'sso_provider': sso_provider,
    })


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
        messages.success(request, f'User {user.email} created successfully.')
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
# Force password change (first login)
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
                profile.must_change_password = False
                profile.save(update_fields=['must_change_password'])
                # Re-login so the session stays valid after password change
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


class RpPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'
