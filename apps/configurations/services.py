import logging

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

from .encryption import encrypt_value, decrypt_value, delete_secret
from .models import Configuration

logger = logging.getLogger(__name__)

CONFIGURATION_DEFAULTS = {
    # Holidays
    "DEFAULT_HOLIDAYS": {
        "label": "Default holidays per financial year.",
        "value": "20",
        "description": (
            "Number of holiday days allocated to each team member per financial year. "
            "Used as the baseline when calculating available capacity in sprint planning."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "DEFAULT_HOLIDAYS_PER_SPRINT": {
        "label": "Default holidays per sprint (placeholder engineers)",
        "value": "0",
        "description": (
            "Number of holiday/absence days applied per sprint when generating absence records "
            "for hire placeholder engineers. Defaults to 0 (no absences generated)."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    # Financial Years
    "FY_EXPIRY_WARNING_DAYS": {
        "label": "FY Expiry Warning (days)",
        "value": "30",
        "description": (
            "When the active financial year has fewer than this many days remaining, "
            "a warning banner is displayed at the top of every page and the remaining "
            "days cell is highlighted in the Financial Years list."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    # Sprints
    "SPRINT_NAME_PREFIX": {
        "label": "Sprint Name Prefix",
        "value": "Sprint",
        "description": (
            "Prefix used when auto-generating sprint names. "
            "For example, 'Sprint', 'SP', etc."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SPRINT_START_NUMBER": {
        "label": "Sprint Start Number",
        "value": "1",
        "description": (
            "The starting number used when generating the first sprint of a financial year "
            "if no existing sprints are found."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "SPRINT_DURATION_DAYS": {
        "label": "Sprint Duration (days)",
        "value": "14",
        "description": (
            "Number of calendar days in a sprint. "
            "Typically set to 14 days (2 weeks)."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "SPRINT_POINT_PRICE": {
        "label": "Sprint Point Price (£)",
        "value": "1150",
        "description": (
            "Day rate in GBP (£) used for calculating sprint cost based on story points. "
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    # Projects
    "BUDGET_THRESHOLD_PCT_DEFAULT": {
        "label": "Budget Threshold %",
        "value": "10",
        "description": (
            "Percentage band used to classify budget risk. "
            "Remaining > +threshold% = GREEN, within ±threshold% = AMBER, "
            "below -threshold% = RED."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "BUDGET_SIZE_XS_MAX_AMOUNT": {
        "label": "T-Shirt Size XS Upper Boundary (£)",
        "value": "20000",
        "description": (
            "Maximum actual budget (inclusive) to classify a budget or estimate as X-Small. "
            "Default £20,000."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "BUDGET_SIZE_S_MAX_AMOUNT": {
        "label": "T-Shirt Size S Upper Boundary (£)",
        "value": "60000",
        "description": (
            "Maximum actual budget (inclusive) to classify a budget or estimate as Small. "
            "Default £60,000."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "BUDGET_SIZE_M_MAX_AMOUNT": {
        "label": "T-Shirt Size M Upper Boundary (£)",
        "value": "200000",
        "description": (
            "Maximum actual budget (inclusive) to classify a budget or estimate as Medium. "
            "Default £200,000."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "BUDGET_SIZE_L_MAX_AMOUNT": {
        "label": "T-Shirt Size L Upper Boundary (£)",
        "value": "500000",
        "description": (
            "Maximum actual budget (inclusive) to classify a budget or estimate as Large. "
            "Default £500,000. Anything above is X-Large."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "BUDGET_SIZE_XS_GREEN_PCT": {
        "label": "T-Shirt Size XS Green Threshold (%)",
        "value": "0.25",
        "description": (
            "Variance % within which an XS budget/estimate is considered On Budget (GREEN). "
            "Default 0.25%."
        ),
        "data_type": "float",
        "is_secret": False,
    },
    "BUDGET_SIZE_S_GREEN_PCT": {
        "label": "T-Shirt Size S Green Threshold (%)",
        "value": "0.50",
        "description": (
            "Variance % within which a Small budget/estimate is considered On Budget (GREEN). "
            "Default 0.50%."
        ),
        "data_type": "float",
        "is_secret": False,
    },
    "BUDGET_SIZE_M_GREEN_PCT": {
        "label": "T-Shirt Size M Green Threshold (%)",
        "value": "1.00",
        "description": (
            "Variance % within which a Medium budget/estimate is considered On Budget (GREEN). "
            "Default 1.00%."
        ),
        "data_type": "float",
        "is_secret": False,
    },
    "BUDGET_SIZE_L_GREEN_PCT": {
        "label": "T-Shirt Size L Green Threshold (%)",
        "value": "1.00",
        "description": (
            "Variance % within which a Large budget/estimate is considered On Budget (GREEN). "
            "Default 1.00%."
        ),
        "data_type": "float",
        "is_secret": False,
    },
    "BUDGET_SIZE_XL_GREEN_PCT": {
        "label": "T-Shirt Size XL Green Threshold (%)",
        "value": "1.00",
        "description": (
            "Variance % within which an XL budget/estimate is considered On Budget (GREEN). "
            "Default 1.00%."
        ),
        "data_type": "float",
        "is_secret": False,
    },
    # AI
    "AI_ENABLED": {
        "label": "AI Enabled",
        "value": "false",
        "description": (
            "Master switch for AI-powered features. "
            "Set to 'true' to enable. When false, all features fall back to "
            "their deterministic implementations. Accepted values: true, false."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    "AI_PROVIDER": {
        "label": "AI Provider",
        "value": "anthropic",
        "description": (
            "AI provider to use. "
            "Accepted values: 'anthropic' (Anthropic API), 'bedrock' (AWS Bedrock). "
            "When set to 'bedrock', the AI_BEDROCK_* configs are also required."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "AI_MODEL": {
        "label": "AI Model",
        "value": "",
        "description": (
            "Model identifier string. "
            "Anthropic example: claude-sonnet-4-20250514. "
            "Bedrock example: anthropic.claude-3-5-sonnet-20241022-v2:0 "
            "(full Bedrock model ID including version suffix)."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "AI_ANTHROPIC_API_KEY": {
        "label": "Anthropic API Key",
        "value": "",
        "description": (
            "Anthropic API key (sk-ant-...). "
            "Required only when AI_PROVIDER=anthropic. "
            "Stored encrypted at rest."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "AI_BEDROCK_REGION": {
        "label": "Bedrock Region",
        "value": "us-east-1",
        "description": (
            "AWS region for Bedrock API calls. "
            "Required when AI_PROVIDER=bedrock. "
            "Must be a region where the chosen model is available. "
            "Examples: us-east-1, eu-west-2, ap-southeast-1."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "AI_BEDROCK_AUTH_MODE": {
        "label": "Bedrock Auth Mode",
        "value": "role",
        "description": (
            "Authentication mode for AWS Bedrock. "
            "'role' — no credentials stored; boto3 resolves via instance profile, "
            "ECS task role, or AWS_* environment variables. "
            "'user' — explicit IAM user credentials stored in AI_BEDROCK_IAM_KEY "
            "and AI_BEDROCK_IAM_SECRET. Use 'user' for local or on-premise deployments."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "AI_BEDROCK_IAM_KEY": {
        "label": "Bedrock IAM Access Key ID",
        "value": "",
        "description": (
            "AWS IAM user access key ID. "
            "Required only when AI_PROVIDER=bedrock and AI_BEDROCK_AUTH_MODE=user. "
            "The IAM user must have bedrock:InvokeModel permission on the chosen model. "
            "Stored encrypted at rest."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "AI_BEDROCK_IAM_SECRET": {
        "label": "Bedrock IAM Secret Access Key",
        "value": "",
        "description": (
            "AWS IAM user secret access key. "
            "Required only when AI_PROVIDER=bedrock and AI_BEDROCK_AUTH_MODE=user. "
            "Stored encrypted at rest."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    # Authentication
    "AUTH_MODE": {
        "label": "Authentication Mode",
        "value": "classic",
        "description": (
            "Controls how users authenticate. "
            "'classic' — username and password via the built-in login screen. "
            "'sso' — redirect to the configured identity provider; no local login screen."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "ALLOW_REGISTRATION": {
        "label": "Allow Self-Registration",
        "value": "true",
        "description": (
            "When AUTH_MODE=classic, allow new users to create their own account "
            "via the /register/ page. Set to 'false' to restrict access to admin-created accounts only."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    "SESSION_TIMEOUT_MINUTES": {
        "label": "Session Timeout (minutes)",
        "value": "480",
        "description": (
            "Number of idle minutes before an authenticated session expires and the user "
            "is redirected to the login page. Default: 480 (8 hours)."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    # SSO — General
    "SSO_PROTOCOL": {
        "label": "SSO Protocol",
        "value": "oauth2",
        "description": (
            "SSO protocol to use when AUTH_MODE=sso. "
            "'oauth2' — OpenID Connect / OAuth2 (GitHub, Azure AD, Google, Okta, etc.). "
            "'saml' — SAML 2.0 (Azure AD SAML, Okta SAML, ADFS, etc.)."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_PROVIDER_NAME": {
        "label": "SSO Provider Name",
        "value": "",
        "description": (
            "Display name of the identity provider shown on the login page and welcome message, "
            "e.g. 'GitHub', 'Azure AD', 'Google', 'Okta'."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    # SSO — OAuth2 / OpenID Connect
    "SSO_OAUTH2_CLIENT_ID": {
        "label": "OAuth2 Client ID",
        "value": "",
        "description": (
            "Client (application) ID issued by the identity provider. "
            "Required when SSO_PROTOCOL=oauth2."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "SSO_OAUTH2_CLIENT_SECRET": {
        "label": "OAuth2 Client Secret",
        "value": "",
        "description": (
            "Client secret issued by the identity provider. "
            "Required when SSO_PROTOCOL=oauth2."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "SSO_OAUTH2_AUTH_URL": {
        "label": "OAuth2 Authorization Endpoint",
        "value": "",
        "description": (
            "The identity provider's authorization URL where users are redirected to authenticate. "
            "Example (GitHub): https://github.com/login/oauth/authorize. "
            "Example (Azure AD): https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_OAUTH2_TOKEN_URL": {
        "label": "OAuth2 Token Endpoint",
        "value": "",
        "description": (
            "The identity provider's token URL used to exchange the authorization code for tokens. "
            "Example (GitHub): https://github.com/login/oauth/access_token. "
            "Example (Azure AD): https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_OAUTH2_USERINFO_URL": {
        "label": "OAuth2 User Info Endpoint",
        "value": "",
        "description": (
            "URL to fetch the authenticated user's profile. "
            "Example (GitHub): https://api.github.com/user. "
            "Example (Azure AD): https://graph.microsoft.com/oidc/userinfo. "
            "Leave blank for providers that include claims in the ID token."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_OAUTH2_SCOPE": {
        "label": "OAuth2 Scope",
        "value": "openid email profile",
        "description": (
            "Space-separated OAuth2 scopes to request. "
            "Typical: 'openid email profile'. "
            "GitHub does not use OpenID Connect — use 'user:email read:user' instead."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    # SSO — SAML 2.0
    "SSO_SAML_IDP_ENTITY_ID": {
        "label": "SAML IdP Entity ID",
        "value": "",
        "description": (
            "The identity provider's entity ID (Issuer). Found in the IdP metadata XML. "
            "Example (Azure AD): https://sts.windows.net/{tenant-id}/."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_SAML_IDP_SSO_URL": {
        "label": "SAML IdP SSO URL",
        "value": "",
        "description": (
            "The identity provider's Single Sign-On URL (HTTP-Redirect binding). "
            "Example (Azure AD): https://login.microsoftonline.com/{tenant}/saml2."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_SAML_IDP_CERT": {
        "label": "SAML IdP X.509 Certificate",
        "value": "",
        "description": (
            "The identity provider's public X.509 certificate (PEM or base64, without header/footer). "
            "Used to verify the SAML assertion signature."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "SSO_SAML_SP_ENTITY_ID": {
        "label": "SAML SP Entity ID",
        "value": "",
        "description": (
            "This application's entity ID registered with the identity provider. "
            "Typically the application's base URL, e.g. https://resourceplanner.example.com/."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "SSO_SAML_SP_ACS_URL": {
        "label": "SAML SP Assertion Consumer Service URL",
        "value": "",
        "description": (
            "The URL the identity provider posts the SAML response to after authentication. "
            "Typically: https://resourceplanner.example.com/sso/saml/acs/. "
            "Leave blank to auto-detect from the request host."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    # Password policy
    "PASSWORD_MIN_LENGTH": {
        "label": "Password Minimum Length",
        "value": "8",
        "description": (
            "Minimum number of characters required for user passwords. "
            "Applies to registration, password change, and admin-created accounts."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "PASSWORD_REQUIRE_UPPERCASE": {
        "label": "Require Uppercase Letter",
        "value": "false",
        "description": (
            "When true, passwords must contain at least one uppercase letter (A–Z)."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    "PASSWORD_REQUIRE_LOWERCASE": {
        "label": "Require Lowercase Letter",
        "value": "false",
        "description": (
            "When true, passwords must contain at least one lowercase letter (a–z)."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    "PASSWORD_REQUIRE_DIGITS": {
        "label": "Require Digit",
        "value": "false",
        "description": (
            "When true, passwords must contain at least one digit (0–9)."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    "PASSWORD_REQUIRE_SPECIAL": {
        "label": "Require Special Character",
        "value": "false",
        "description": (
            "When true, passwords must contain at least one special character "
            "(!@#$%^&*…)."
        ),
        "data_type": "boolean",
        "is_secret": False,
    },
    # Email (outbound mail)
    "EMAIL_PROTOCOL": {
        "label": "Email Protocol",
        "value": "console",
        "description": (
            "Outbound email protocol. "
            "'console' — prints to server log (development only). "
            "'smtp' — plain SMTP (no encryption). "
            "'smtp_tls' — SMTP with STARTTLS (common for port 587). "
            "'smtp_ssl' — SMTP over SSL (common for port 465)."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "EMAIL_HOST": {
        "label": "Email Host (SMTP Server)",
        "value": "localhost",
        "description": (
            "Hostname or IP address of the outbound SMTP server. "
            "Examples: smtp.gmail.com, smtp.office365.com, mail.example.com."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "EMAIL_PORT": {
        "label": "Email Port",
        "value": "25",
        "description": (
            "TCP port for the SMTP server. "
            "Common values: 25 (unencrypted), 465 (SSL), 587 (STARTTLS)."
        ),
        "data_type": "integer",
        "is_secret": False,
    },
    "EMAIL_HOST_USER": {
        "label": "Email Username",
        "value": "",
        "description": (
            "Username (or email address) used to authenticate with the SMTP server. "
            "Leave blank if the server does not require authentication."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    "EMAIL_HOST_PASSWORD": {
        "label": "Email Password",
        "value": "",
        "description": (
            "Password used to authenticate with the SMTP server. "
            "Stored encrypted at rest."
        ),
        "data_type": "string",
        "is_secret": True,
    },
    "EMAIL_FROM": {
        "label": "From Email Address",
        "value": "noreply@resourceplanner.local",
        "description": (
            "The 'From' address used for all outbound emails (password resets, "
            "notifications, etc.)."
        ),
        "data_type": "string",
        "is_secret": False,
    },
    # Add future built-in configs as below
    # "CODE": {
    #   "label": "Human readable label for the config.",
    #   "value": "default value",
    #   "description": "Information on how this config is used.",
    #   "data_type": "string",   # string | integer | float | boolean
    #   "is_secret": False,
    # }
}


class ConfigurationService:
    @staticmethod
    def list_configurations(filters=None, page=1, page_size=20):
        """
        List the configurations.
        Supports filters: search
        """
        VALID_ORDER_FIELDS = {"code"}
        qs = Configuration.objects.all()

        if filters:
            if filters.get("search"):
                s_term = filters["search"]
                qs = (
                    qs.filter(code__icontains=s_term)
                    | qs.filter(label__icontains=s_term)
                    | qs.filter(description__icontains=s_term)
                )

        order_by = filters.get("order_by") if filters else None
        order_dir = filters.get("order_dir") if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else "code"
        if order_dir == "desc":
            order_field = f"-{order_field}"
        qs = qs.order_by(order_field)

        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    def list_stats(fields=None):
        """
        List the statistics of the configurations.
        Supports filters: fields
        """
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        qs = Configuration.objects.all()
        result = {}

        if wants("total_configurations"):
            result["total_configurations"] = qs.count()

        return result

    @staticmethod
    def get_configuration(config_id: int):
        """
        Returns the details of the specified configuration id.
        """
        if not config_id:
            raise ValidationError(
                "Invalid: config_id must be an integer and greater than 0."
            )

        return Configuration.objects.get(pk=config_id)

    @staticmethod
    def get_configuration_by_code(code: str):
        """
        Returns the details of the specified configuration code.
        """
        if not code:
            raise ValidationError("Invalid: code cannot be blank.")

        u_code = code.strip().upper()
        if not u_code:
            raise ValidationError("Invalid: code cannot be blank.")

        return Configuration.objects.get(code=u_code)

    @staticmethod
    def get_default_configuration_value(code: str):
        """
        Returns the default value of the specified configuration code.
        """
        if not code:
            raise ValidationError("Invalid: code cannot be blank.")

        u_code = code.strip().upper()
        if not u_code:
            raise ValidationError("Invalid: code cannot be blank.")

        entry = CONFIGURATION_DEFAULTS.get(u_code)
        return entry.get("value") if entry else None

    @staticmethod
    @transaction.atomic
    def update_configuration(config_id: int, value: str):
        """
        Updates the specified configuration id.
        For secret configs, encrypts the value before saving.
        Passing an empty value for a secret config is a no-op (existing value preserved).
        """
        if not config_id:
            raise ValidationError(
                "Invalid: config_id must be an integer and greater than 0."
            )

        config = Configuration.objects.get(pk=config_id)
        if not config:
            raise ValidationError(f"Configuration '{config_id}' does not exist.")

        if config.is_secret:
            if value:
                config.value = encrypt_value(value, config.code)
            # else: empty → keep existing encrypted value unchanged
        else:
            config.value = value

        try:
            config.full_clean()
            config.save(update_fields=["value", "updated_at"])
            return config
        except IntegrityError as e:
            logger.error(
                "Database error when updating configuration '%s': %s", config_id, e
            )
            raise ValidationError(
                f"Configuration '{config_id}' could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "Database error when updating configuration '%s': %s", config_id, e
            )
            raise RuntimeError(
                f"A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when updating configuration '%s': %s", config_id, e
            )
            raise

    @staticmethod
    @transaction.atomic
    def reset_to_default(config_id: int):
        """
        Resets the configuration to default for the specified configuration id.
        For secret configs, any backing secret store entry is cleaned up.
        """
        if not config_id:
            raise ValidationError(
                "Invalid: config_id must be an integer and greater than 0."
            )

        config = Configuration.objects.get(pk=config_id)
        if not config:
            raise ValidationError(f"Configuration '{config_id}' does not exist.")

        default = CONFIGURATION_DEFAULTS.get(config.code)
        if default is None:
            raise ValidationError(
                f"No factory default is registered for '{config.code}'."
            )

        if config.is_secret:
            delete_secret(config.code, config.value)

        config.value = default["value"]

        try:
            config.full_clean()
            config.save(update_fields=["value", "updated_at"])
            return config
        except IntegrityError as e:
            logger.error(
                "Database error when resetting configuration to default '%s': %s",
                config_id,
                e,
            )
            raise ValidationError(
                f"Configuration '{config_id}' could not be updated due to a conflict."
            ) from e
        except DatabaseError as e:
            logger.exception(
                "Database error when resetting configuration to default '%s': %s",
                config_id,
                e,
            )
            raise RuntimeError(
                f"A database error occurred. Please try again later."
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error when resetting configuration to default '%s': %s",
                config_id,
                e,
            )
            raise

    @staticmethod
    def _read_value(cfg: Configuration) -> str:
        """Return the plaintext value, decrypting secrets automatically."""
        if cfg.is_secret:
            return decrypt_value(cfg.value, cfg.code)
        return cfg.value

    @staticmethod
    def get_int(code: str, fallback: int = 0) -> int:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return int(ConfigurationService._read_value(cfg))
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_str(code: str, fallback: str = "") -> str:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return ConfigurationService._read_value(cfg)
        except ObjectDoesNotExist:
            return fallback

    @staticmethod
    def get_float(code: str, fallback: float = 0.0) -> float:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return float(ConfigurationService._read_value(cfg))
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_bool(code: str, fallback: bool = False) -> bool:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return ConfigurationService._read_value(cfg).strip().lower() in ("1", "true", "yes", "on")
        except ObjectDoesNotExist:
            return fallback
