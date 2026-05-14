import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .models import UserProfile, UserGroup, UserGroupMembership
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    UserGroupSerializer, UserGroupCreateSerializer, UserGroupMemberSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


class UserViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ── List ────────────────────────────────────────────────────────────────
    def list(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)

        qs = User.objects.select_related('profile').order_by('email')

        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        is_active = request.query_params.get('is_active')
        if is_active in ('true', 'false'):
            qs = qs.filter(is_active=(is_active == 'true'))

        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 25

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)

        serializer = UserSerializer(page_obj.object_list, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'pagination': {
                'total_count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'page_size': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            },
        })

    # ── Create ───────────────────────────────────────────────────────────────
    def create(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)

        ser = UserCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response({'error': 'Validation failed.', 'details': ser.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = ser.save()
        except Exception as exc:
            logger.exception('User create failed: %s', exc)
            return _err('Could not create user.', status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(UserSerializer(user, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    # ── Retrieve ─────────────────────────────────────────────────────────────
    def retrieve(self, request, pk=None):
        user = self._get_user(request, pk)
        if isinstance(user, Response):
            return user
        return Response(UserSerializer(user, context={'request': request}).data)

    # ── Update ───────────────────────────────────────────────────────────────
    def partial_update(self, request, pk=None):
        user = self._get_user(request, pk)
        if isinstance(user, Response):
            return user

        ser = UserUpdateSerializer(data=request.data, instance=user)
        if not ser.is_valid():
            return Response({'error': 'Validation failed.', 'details': ser.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        if not request.user.is_staff and any(f in request.data for f in ('is_staff', 'is_active')):
            return _err('Only admins can change role or active status.', status.HTTP_403_FORBIDDEN)

        updated = ser.update(user, ser.validated_data)
        return Response(UserSerializer(updated, context={'request': request}).data)

    # ── Delete ───────────────────────────────────────────────────────────────
    def destroy(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)

        if user == request.user:
            return _err('You cannot delete your own account.', status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── /me ──────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        return Response(UserSerializer(request.user, context={'request': request}).data)

    # ── /me/update ───────────────────────────────────────────────────────────
    @action(detail=False, methods=['patch'], url_path='me/update')
    def me_update(self, request):
        ser = UserUpdateSerializer(data=request.data, instance=request.user)
        if not ser.is_valid():
            return Response({'error': 'Validation failed.', 'details': ser.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        # Non-admins cannot change role/active status for themselves
        restricted = ('is_staff', 'is_active', 'is_superuser')
        for f in restricted:
            ser.validated_data.pop(f, None)

        updated = ser.update(request.user, ser.validated_data)
        return Response(UserSerializer(updated, context={'request': request}).data)

    # ── /me/change_password ──────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='me/change_password')
    def me_change_password(self, request):
        user = request.user
        current = request.data.get('current_password', '')
        new_pwd = request.data.get('new_password', '')

        if not user.check_password(current):
            return _err('Current password is incorrect.')

        try:
            validate_password(new_pwd, user=user)
        except DjangoValidationError as exc:
            return Response({'error': 'Password validation failed.',
                             'details': {'new_password': list(exc.messages)}},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_pwd)
        user.save()
        return Response({'message': 'Password updated successfully.'})

    # ── /me/upload_avatar ────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='me/upload_avatar',
            parser_classes=[MultiPartParser, FormParser])
    def me_upload_avatar(self, request):
        file = request.FILES.get('avatar')
        if not file:
            return _err('No file provided.')

        if file.size > 5 * 1024 * 1024:
            return _err('Avatar must be smaller than 5 MB.')

        content_type = getattr(file, 'content_type', '')
        if not content_type.startswith('image/'):
            return _err('Only image files are accepted.')

        try:
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'sso_provider': '', 'sso_uid': ''},
            )
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = file
            profile.save(update_fields=['avatar'])
        except Exception as exc:
            logger.exception('Avatar upload failed: %s', exc)
            return _err('Could not save avatar.', status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(UserSerializer(request.user, context={'request': request}).data)

    # ── /me/remove_avatar ────────────────────────────────────────────────────
    @action(detail=False, methods=['delete'], url_path='me/remove_avatar')
    def me_remove_avatar(self, request):
        try:
            profile = request.user.profile
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
                profile.save(update_fields=['avatar'])
            profile.avatar_url = ''
            profile.save(update_fields=['avatar_url'])
        except UserProfile.DoesNotExist:
            pass
        return Response(UserSerializer(request.user, context={'request': request}).data)

    # ── /{pk}/deactivate ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)
        if user == request.user:
            return _err('You cannot deactivate your own account.')
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user, context={'request': request}).data)

    # ── /{pk}/activate ───────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user, context={'request': request}).data)

    # ── /{pk}/reset_password (admin) ─────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='reset_password')
    def reset_password(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)

        new_pwd = request.data.get('new_password', '')
        if not new_pwd:
            return _err('new_password is required.')

        try:
            validate_password(new_pwd, user=user)
        except DjangoValidationError as exc:
            return Response({'error': 'Password validation failed.',
                             'details': {'new_password': list(exc.messages)}},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_pwd)
        user.save()
        return Response({'message': 'Password reset successfully.'})

    # ── /stats ───────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        total = User.objects.count()
        active = User.objects.filter(is_active=True).count()
        staff = User.objects.filter(is_staff=True).count()
        sso = UserProfile.objects.filter(sso_provider__gt='').count()
        return Response({
            'total': total,
            'active': active,
            'inactive': total - active,
            'staff': staff,
            'sso': sso,
        })

    # ── /switch_auth_mode ────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='switch_auth_mode')
    def switch_auth_mode(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)

        mode = request.data.get('mode', '')
        if mode not in ('classic', 'sso'):
            return _err("mode must be 'classic' or 'sso'.")

        wipe = request.data.get('wipe_passwords', False)

        from apps.configurations.services import ConfigurationService
        ConfigurationService.update_configuration('AUTH_MODE', mode)

        wiped_count = 0
        if mode == 'sso' and wipe:
            classic_users = User.objects.filter(
                profile__sso_provider=''
            ).union(
                User.objects.exclude(profile__isnull=False)
            )
            for user in User.objects.filter(
                profile__isnull=True
            ) | User.objects.filter(profile__sso_provider=''):
                if not user.is_superuser:
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                    wiped_count += 1

        return Response({
            'message': f'Auth mode switched to {mode}.',
            'wiped_passwords': wiped_count,
        })

    # ── helpers ──────────────────────────────────────────────────────────────
    def _get_user(self, request, pk):
        is_self = (str(pk) == str(request.user.pk))
        if not is_self and not request.user.is_staff:
            return _err('Access denied.', status.HTTP_403_FORBIDDEN)
        try:
            return User.objects.select_related('profile').get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# UserGroupViewSet
# ---------------------------------------------------------------------------

def _sync_staff_for_user(user):
    """Set is_staff based on membership in any is_admin_group."""
    if user.is_superuser:
        return  # superusers always keep their access
    in_admin_group = UserGroup.objects.filter(
        is_admin_group=True,
        members=user,
    ).exists()
    if user.is_staff != in_admin_group:
        user.is_staff = in_admin_group
        user.save(update_fields=['is_staff'])


class UserGroupViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        return None

    # ── List ─────────────────────────────────────────────────────────────────
    def list(self, request):
        qs = UserGroup.objects.all()
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        serializer = UserGroupSerializer(qs, many=True)
        return Response({'results': serializer.data, 'total': qs.count()})

    # ── Create ────────────────────────────────────────────────────────────────
    def create(self, request):
        deny = self._require_admin(request)
        if deny:
            return deny
        ser = UserGroupCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response({'error': 'Validation failed.', 'details': ser.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        group = ser.save()
        return Response(UserGroupSerializer(group).data, status=status.HTTP_201_CREATED)

    # ── Retrieve ──────────────────────────────────────────────────────────────
    def retrieve(self, request, pk=None):
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)
        return Response(UserGroupSerializer(group).data)

    # ── Update ────────────────────────────────────────────────────────────────
    def partial_update(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        ser = UserGroupSerializer(group, data=request.data, partial=True)
        if not ser.is_valid():
            return Response({'error': 'Validation failed.', 'details': ser.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        group = ser.save()

        # Re-sync staff status for all members if is_admin_group changed
        if 'is_admin_group' in request.data:
            for user in group.members.all():
                _sync_staff_for_user(user)

        return Response(UserGroupSerializer(group).data)

    # ── Delete ────────────────────────────────────────────────────────────────
    def destroy(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)
        if group.is_system:
            return _err('System groups cannot be deleted.')
        members = list(group.members.all())
        group.delete()
        for user in members:
            _sync_staff_for_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── /stats ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        total = UserGroup.objects.count()
        admin = UserGroup.objects.filter(is_admin_group=True).count()
        return Response({'total': total, 'admin': admin})

    # ── /{pk}/members ─────────────────────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='members')
    def members(self, request, pk=None):
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        memberships = UserGroupMembership.objects.filter(group=group).select_related('user', 'user__profile')
        result = []
        for m in memberships:
            u = m.user
            u._membership = m
            result.append(u)

        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 25

        paginator = Paginator(result, page_size)
        page_obj = paginator.get_page(page)

        ser = UserGroupMemberSerializer(page_obj.object_list, many=True, context={'request': request})
        return Response({
            'results': ser.data,
            'pagination': {
                'total_count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page_obj.number,
                'page_size': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            },
        })

    # ── /{pk}/add_members ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='add_members')
    def add_members(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list) or not user_ids:
            return _err('user_ids must be a non-empty list.')

        added = []
        for uid in user_ids:
            try:
                user = User.objects.get(pk=uid)
                _, created = UserGroupMembership.objects.get_or_create(user=user, group=group)
                if created:
                    added.append(uid)
                    if group.is_admin_group:
                        _sync_staff_for_user(user)
            except User.DoesNotExist:
                pass

        return Response({'added': added, 'member_count': group.members.count()})

    # ── /{pk}/remove_members ──────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='remove_members')
    def remove_members(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny
        try:
            group = UserGroup.objects.get(pk=pk)
        except UserGroup.DoesNotExist:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list) or not user_ids:
            return _err('user_ids must be a non-empty list.')

        removed = []
        for uid in user_ids:
            deleted, _ = UserGroupMembership.objects.filter(
                user_id=uid, group=group
            ).delete()
            if deleted:
                removed.append(uid)
                try:
                    user = User.objects.get(pk=uid)
                    _sync_staff_for_user(user)
                except User.DoesNotExist:
                    pass

        return Response({'removed': removed, 'member_count': group.members.count()})
