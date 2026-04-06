def parse_bool(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() == "true"


def view_set_validation_details(e):
    from rest_framework.exceptions import ValidationError as DRFValidationError

    if isinstance(e, DRFValidationError):
        return e.detail

    try:
        return e.message_dict
    except AttributeError:
        return e.messages
