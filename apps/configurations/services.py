import logging

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction

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
        )
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
    },
    # Sprints
    "SPRINT_NAME_PREFIX": {
        "label": "Sprint Name Prefix",
        "value": "Sprint",
        "description": (
            "Prefix used when auto-generating sprint names. "
            "For example, 'Sprint', 'SP', etc."
        ),
    },
    "SPRINT_START_NUMBER": {
        "label": "Sprint Start Number",
        "value": "1",
        "description": (
            "The starting number used when generating the first sprint of a financial year "
            "if no existing sprints are found."
        ),
    },
    "SPRINT_DURATION_DAYS": {
        "label": "Sprint Duration (days)",
        "value": "14",
        "description": (
            "Number of calendar days in a sprint. "
            "Typically set to 14 days (2 weeks)."
        ),
    },
    "SPRINT_POINT_PRICE": {
        "label": "Sprint Point Price (£)",
        "value": "1150",
        "description": (
            "Day rate in GBP (£) used for calculating sprint cost based on story points. "
        ),
    },
    # Add future built-in configs as below
    # "CODE": {
    #   "label": "Human readable label for the config.",
    #   "value": "default value",
    #   "description": "Information on how this config is used.",
    # }
}


class ConfigurationService:
    @staticmethod
    def list_configurations(filters=None, page=1, page_size=20):
        """
        List the configurations.
        Supports filters: search
        """
        VALID_ORDER_FIELDS = {'code'}
        qs = Configuration.objects.all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = qs.filter(code__icontains=s_term) | qs.filter(label__icontains=s_term) | qs.filter(
                    description__icontains=s_term)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'code'
        if order_dir == 'desc':
            order_field = f'-{order_field}'
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
            raise ValidationError("Invalid: config_id must be an integer and greater than 0.")

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
        return entry.get('value') if entry else None

    @staticmethod
    @transaction.atomic
    def update_configuration(config_id: int, value: str):
        """
        Updates the specified configuration id.
        """
        if not config_id:
            raise ValidationError("Invalid: config_id must be an integer and greater than 0.")

        config = Configuration.objects.get(pk=config_id)
        if not config:
            raise ValidationError(f"Configuration '{config_id}' does not exist.")

        config.value = value

        try:
            config.full_clean()
            config.save(update_fields=['value', 'updated_at'])
            return config
        except IntegrityError as e:
            logger.error("Database error when updating configuration '%s': %s", config_id, e)
            raise ValidationError(f"Configuration '{config_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating configuration '%s': %s", config_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating configuration '%s': %s", config_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def reset_to_default(config_id: int):
        """
        Resets the configuration to default for the specified configuration id.
        """
        if not config_id:
            raise ValidationError("Invalid: config_id must be an integer and greater than 0.")

        config = Configuration.objects.get(pk=config_id)
        if not config:
            raise ValidationError(f"Configuration '{config_id}' does not exist.")

        default = CONFIGURATION_DEFAULTS.get(config.code)
        if default is None:
            raise ValidationError(f"No factory default is registered for '{config.code}'.")

        config.value = default['value']

        try:
            config.full_clean()
            config.save(update_fields=['value', 'updated_at'])
            return config
        except IntegrityError as e:
            logger.error("Database error when resetting configuration to default '%s': %s", config_id, e)
            raise ValidationError(f"Configuration '{config_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when resetting configuration to default '%s': %s", config_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when resetting configuration to default '%s': %s", config_id, e)
            raise

    @staticmethod
    def get_int(code: str, fallback: int = 0) -> int:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return int(cfg.value)
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_str(code: str, fallback: str = '') -> str:
        try:
            return Configuration.objects.get(code=code.strip().upper()).value
        except ObjectDoesNotExist:
            return fallback

    @staticmethod
    def get_float(code: str, fallback: float = 0.0) -> float:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return float(cfg.value)
        except (ObjectDoesNotExist, ValueError, TypeError):
            return fallback

    @staticmethod
    def get_bool(code: str, fallback: bool = False) -> bool:
        try:
            cfg = Configuration.objects.get(code=code.strip().upper())
            return cfg.value.strip().lower() in ('1', 'true', 'yes', 'on')
        except ObjectDoesNotExist:
            return fallback
