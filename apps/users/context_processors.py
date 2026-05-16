import json


def user_perms_js(request):
    if not request.user.is_authenticated:
        return {'user_perms_json': '[]'}
    perms = sorted(request.user.get_all_permissions())
    return {'user_perms_json': json.dumps(perms)}


def app_settings(request):
    if not request.user.is_authenticated:
        return {'app_name': 'Resource<b>Planner</b>', 'session_timeout_minutes': 480}
    try:
        from apps.configurations.services import ConfigurationService
        app_name = ConfigurationService.get_str('APP_NAME', 'Resource<b>Planner</b>')
        timeout_minutes = ConfigurationService.get_int('SESSION_TIMEOUT_MINUTES', 480)
    except Exception:
        app_name = 'Resource<b>Planner</b>'
        timeout_minutes = 480
    return {
        'app_name': app_name,
        'session_timeout_minutes': timeout_minutes,
    }
