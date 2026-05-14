from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

_INPUT_CLS = 'form-control rp-input'


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'autofocus': True,
            'autocomplete': 'email',
            'class': _INPUT_CLS,
            'placeholder': 'you@example.com',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': _INPUT_CLS,
            'placeholder': 'Password',
        }),
    )
    remember_me = forms.BooleanField(required=False)


class RegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'First name', 'autofocus': True}),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': _INPUT_CLS, 'placeholder': 'you@example.com', 'autocomplete': 'email'}),
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Password', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Confirm password', 'autocomplete': 'new-password'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email address already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1', '')
        p2 = cleaned.get('password2', '')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        if p1:
            try:
                validate_password(p1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned

    def save(self):
        email = self.cleaned_data['email']
        username = email[:150]
        # Ensure username uniqueness if needed
        if User.objects.filter(username=username).exists():
            import secrets
            username = f'{email[:140]}{secrets.token_hex(4)}'
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            password=self.cleaned_data['password1'],
        )
        return user


class ProfileForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': _INPUT_CLS, 'placeholder': 'you@example.com'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if self._user and User.objects.filter(email__iexact=email).exclude(pk=self._user.pk).exists():
            raise ValidationError('Another account is using this email address.')
        return email


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Current password', 'autocomplete': 'current-password'}),
    )
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'New password', 'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Confirm new password', 'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_current_password(self):
        pwd = self.cleaned_data['current_password']
        if self._user and not self._user.check_password(pwd):
            raise ValidationError('Current password is incorrect.')
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1', '')
        p2 = cleaned.get('new_password2', '')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password2', 'Passwords do not match.')
        if p1:
            try:
                validate_password(p1, user=self._user)
            except ValidationError as exc:
                self.add_error('new_password1', exc)
        return cleaned


class AdminUserCreateForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': _INPUT_CLS, 'placeholder': 'you@example.com'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': _INPUT_CLS, 'placeholder': 'Password', 'autocomplete': 'new-password'}),
    )
    is_staff = forms.BooleanField(required=False, label='Admin / staff access')

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_password(self):
        pwd = self.cleaned_data['password']
        try:
            validate_password(pwd)
        except ValidationError as exc:
            raise ValidationError(exc.messages)
        return pwd

    def save(self):
        email = self.cleaned_data['email']
        username = email[:150]
        if User.objects.filter(username=username).exists():
            import secrets
            username = f'{email[:140]}{secrets.token_hex(4)}'
        return User.objects.create_user(
            username=username,
            email=email,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data.get('last_name', ''),
            password=self.cleaned_data['password'],
            is_staff=self.cleaned_data.get('is_staff', False),
        )
