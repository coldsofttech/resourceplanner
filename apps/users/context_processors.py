import json


def user_perms_js(request):
    if not request.user.is_authenticated:
        return {'user_perms_json': '[]'}
    perms = sorted(request.user.get_all_permissions())
    return {'user_perms_json': json.dumps(perms)}
