from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RefreshToken

ACCESS_TOKEN_EXPIRY = 3600  # seconds


class LoginView(APIView):
    """POST /api/v1/auth/login — exchange credentials for Bearer tokens."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get('username') or request.data.get('email', '')
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {'error': 'username and password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {'error': 'Account is disabled'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token, _ = Token.objects.get_or_create(user=user)
        refresh_token = _get_or_rotate_refresh_token(user)

        return Response({
            'access_token': access_token.key,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TOKEN_EXPIRY,
            'refresh_token': refresh_token.key,
        })


class RefreshView(APIView):
    """POST /api/v1/auth/refresh — exchange a refresh token for new tokens."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        key = request.data.get('refresh_token', '')
        if not key:
            return Response(
                {'error': 'refresh_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rt = RefreshToken.objects.select_related('user').get(key=key)
        except RefreshToken.DoesNotExist:
            return Response(
                {'error': 'Invalid refresh token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if rt.is_expired():
            rt.delete()
            return Response(
                {'error': 'Refresh token expired — please log in again'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = rt.user
        # Rotate access token
        Token.objects.filter(user=user).delete()
        access_token = Token.objects.create(user=user)
        # Rotate refresh token
        rt.rotate()

        return Response({
            'access_token': access_token.key,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TOKEN_EXPIRY,
            'refresh_token': rt.key,
        })


def _get_or_rotate_refresh_token(user):
    try:
        rt = RefreshToken.objects.get(user=user)
        if rt.is_expired():
            rt.rotate()
    except RefreshToken.DoesNotExist:
        rt = RefreshToken.objects.create(
            user=user,
            key=RefreshToken.generate_key(),
            expires_at=timezone.now() + timedelta(days=RefreshToken.REFRESH_EXPIRY_DAYS),
        )
    return rt
