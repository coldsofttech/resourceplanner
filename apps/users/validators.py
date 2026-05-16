from django.core.exceptions import ValidationError


class ConfigurationPasswordValidator:
    """
    Password policy driven by Configurations DB values.
    Falls back to safe defaults if the DB is unavailable.
    """

    def _cfg_int(self, key, fallback):
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_int(key, fallback)
        except Exception:
            return fallback

    def _cfg_bool(self, key, fallback):
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_bool(key, fallback)
        except Exception:
            return fallback

    def validate(self, password, user=None):
        # SSO users are not subject to classic password policies
        if user is not None:
            try:
                if user.profile.sso_provider:
                    return
            except Exception:
                pass

        errors = []

        min_len = self._cfg_int('PASSWORD_MIN_LENGTH', 8)
        if len(password) < min_len:
            errors.append(ValidationError(
                f'Password must be at least %(min)d characters long.',
                code='password_too_short',
                params={'min': min_len},
            ))

        if self._cfg_bool('PASSWORD_REQUIRE_UPPERCASE', False):
            if not any(c.isupper() for c in password):
                errors.append(ValidationError(
                    'Password must contain at least one uppercase letter.',
                    code='password_no_upper',
                ))

        if self._cfg_bool('PASSWORD_REQUIRE_LOWERCASE', False):
            if not any(c.islower() for c in password):
                errors.append(ValidationError(
                    'Password must contain at least one lowercase letter.',
                    code='password_no_lower',
                ))

        if self._cfg_bool('PASSWORD_REQUIRE_DIGITS', False):
            if not any(c.isdigit() for c in password):
                errors.append(ValidationError(
                    'Password must contain at least one digit (0–9).',
                    code='password_no_digit',
                ))

        if self._cfg_bool('PASSWORD_REQUIRE_SPECIAL', False):
            specials = set('!@#$%^&*()_+-=[]{}|;:\'",.<>?/`~\\')
            if not any(c in specials for c in password):
                errors.append(ValidationError(
                    'Password must contain at least one special character (!@#$%^&*…).',
                    code='password_no_special',
                ))

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        min_len = self._cfg_int('PASSWORD_MIN_LENGTH', 8)
        parts = [f'at least {min_len} characters']
        if self._cfg_bool('PASSWORD_REQUIRE_UPPERCASE', False):
            parts.append('one uppercase letter')
        if self._cfg_bool('PASSWORD_REQUIRE_LOWERCASE', False):
            parts.append('one lowercase letter')
        if self._cfg_bool('PASSWORD_REQUIRE_DIGITS', False):
            parts.append('one digit')
        if self._cfg_bool('PASSWORD_REQUIRE_SPECIAL', False):
            parts.append('one special character')
        return 'Your password must contain ' + ', '.join(parts) + '.'
