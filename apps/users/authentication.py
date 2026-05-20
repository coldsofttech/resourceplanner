from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """Accepts 'Authorization: Bearer <token>' in addition to the default 'Token' scheme."""
    keyword = 'Bearer'
