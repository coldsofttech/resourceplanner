import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, RegisterForm

logger = logging.getLogger(__name__)


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
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is not None:
            login(request, user)
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            return redirect(request.POST.get('next') or request.GET.get('next') or '/')
        form.add_error(None, 'Invalid username or password.')

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
        messages.success(request, f'Welcome, {user.first_name or user.username}!')
        return redirect('/')

    return render(request, 'users/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/login/')


# ---------------------------------------------------------------------------
# Password reset — thin wrappers around Django built-ins
# ---------------------------------------------------------------------------

class RpPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.txt'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')


class RpPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'


class RpPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class RpPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'
