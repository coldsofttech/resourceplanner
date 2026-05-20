import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .models import UserProfile, GroupProfile
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    UserGroupSerializer, UserGroupCreateSerializer, UserGroupMemberSerializer,
    _is_admin_by_coverage,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _sync_staff_for_user(user):
    """Set is_staff based on membership in any group with is_admin_group=True."""
    if user.is_superuser:
        return
    in_admin_group = user.groups.filter(profile__is_admin_group=True).exists()
    if user.is_staff != in_admin_group:
        user.is_staff = in_admin_group
        user.save(update_fields=['is_staff'])


def _sync_group_perms_from_categories(group, profile):
    """Recompute group.permissions from its assigned permission_categories only."""
    perm_ids = set()
    for cat in profile.permission_categories.prefetch_related('permissions').all():
        perm_ids.update(cat.permissions.values_list('id', flat=True))
    group.permissions.set(Permission.objects.filter(id__in=perm_ids))


def _check_password_history(user, new_password):
    """Return an error string if new_password matches a recent or current password, else None."""
    try:
        from apps.configurations.services import ConfigurationService
        count = ConfigurationService.get_int('PASSWORD_HISTORY_COUNT', 3)
    except Exception:
        count = 3
    from django.contrib.auth.hashers import check_password
    # Block reusing the current password
    if count > 0 and user.password and check_password(new_password, user.password):
        return 'Your new password must be different from your current password.'
    if count <= 0:
        return None
    from apps.users.models import PasswordHistory
    recent = PasswordHistory.objects.filter(user=user).order_by('-created_at')[:count]
    for entry in recent:
        if check_password(new_password, entry.password_hash):
            return f'You cannot reuse any of your last {count} passwords.'
    return None


def _save_password_history(user, old_hash):
    """Save a previous password hash to history, pruning old entries beyond limit."""
    try:
        from apps.configurations.services import ConfigurationService
        count = ConfigurationService.get_int('PASSWORD_HISTORY_COUNT', 3)
    except Exception:
        count = 3
    if count <= 0:
        return
    from apps.users.models import PasswordHistory
    PasswordHistory.objects.create(user=user, password_hash=old_hash)
    # Prune entries beyond limit
    keep_ids = list(
        PasswordHistory.objects.filter(user=user).order_by('-created_at').values_list('id', flat=True)[:count]
    )
    PasswordHistory.objects.filter(user=user).exclude(id__in=keep_ids).delete()


def _send_invitation_email(user, request):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    try:
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()
    except Exception:
        protocol = 'http'
        domain = 'localhost'

    reset_link = f'{protocol}://{domain}/password-reset/confirm/{uid}/{token}/'

    context = {'user': user, 'reset_link': reset_link}

    from apps.configurations.services import ConfigurationService
    try:
        from_email = ConfigurationService.get_str('EMAIL_FROM', 'noreply@resourceplanner.local')
    except Exception:
        from_email = 'noreply@resourceplanner.local'

    subject = render_to_string('users/invite_email_subject.txt', context).strip()
    message = render_to_string('users/invite_email.txt', context)

    try:
        send_mail(subject, message, from_email, [user.email], fail_silently=True)
    except Exception as exc:
        logger.warning('Failed to send invitation email to %s: %s', user.email, exc)


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
            _send_invitation_email(user, request)
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

        if user.is_superuser and not User.objects.filter(is_superuser=True).exclude(pk=user.pk).exists():
            return _err('Cannot delete the only remaining superuser account.', status.HTTP_403_FORBIDDEN)

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
        restricted = ('is_staff', 'is_active', 'is_superuser')
        for f in restricted:
            ser.validated_data.pop(f, None)

        updated = ser.update(request.user, ser.validated_data)

        # Handle profile-level fields: timezone, theme
        profile_fields = {}
        new_tz = request.data.get('timezone', '').strip()
        if new_tz:
            try:
                import zoneinfo
                zoneinfo.ZoneInfo(new_tz)
                profile_fields['timezone'] = new_tz
            except Exception:
                return _err('Invalid timezone.')
        new_theme = request.data.get('theme', '').strip()
        if new_theme in ('light', 'dark'):
            profile_fields['theme'] = new_theme
        if profile_fields:
            try:
                profile, _ = UserProfile.objects.get_or_create(user=updated)
                for k, v in profile_fields.items():
                    setattr(profile, k, v)
                profile.save(update_fields=list(profile_fields.keys()))
            except Exception as exc:
                logger.warning('Profile field update failed: %s', exc)

        return Response(UserSerializer(updated, context={'request': request}).data)

    # ── /me/change_password ──────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='me/change_password')
    def me_change_password(self, request):
        user = request.user

        # SSO users cannot use classic password change
        try:
            if user.profile.sso_provider:
                return _err('Password change is not available for SSO accounts.', status.HTTP_400_BAD_REQUEST)
        except Exception:
            pass

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

        # Password history check
        history_error = _check_password_history(user, new_pwd)
        if history_error:
            return Response({'error': 'Password validation failed.',
                             'details': {'new_password': [history_error]}},
                            status=status.HTTP_400_BAD_REQUEST)

        old_hash = user.password
        user.set_password(new_pwd)
        user.save()
        _save_password_history(user, old_hash)

        try:
            from django.utils import timezone
            profile = user.profile
            profile.password_last_changed = timezone.now()
            profile.must_change_password = False
            profile.save(update_fields=['password_last_changed', 'must_change_password'])
        except Exception:
            pass

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

        user = User.objects.select_related('profile').get(pk=request.user.pk)
        return Response(UserSerializer(user, context={'request': request}).data)

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

    # ── /me/dashboard_config ─────────────────────────────────────────────────
    @action(detail=False, methods=['get', 'post'], url_path='me/dashboard_config')
    def me_dashboard_config(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if request.method == 'POST':
            config = request.data if isinstance(request.data, (dict, list)) else {}
            profile.dashboard_config = config
            profile.save(update_fields=['dashboard_config'])
        return Response({'dashboard_config': profile.dashboard_config or {}})

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
        if user.is_superuser and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists():
            return _err('Cannot deactivate the only remaining active superuser account.', status.HTTP_403_FORBIDDEN)
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

        try:
            from django.utils import timezone
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.password_last_changed = timezone.now()
            profile.must_change_password = False
            profile.save(update_fields=['password_last_changed', 'must_change_password'])
        except Exception:
            pass

        return Response({'message': 'Password reset successfully.'})

    # ── /{pk}/set_groups ─────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='set_groups')
    def set_groups(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)

        group_ids = request.data.get('group_ids', [])
        if not isinstance(group_ids, list):
            return _err('group_ids must be a list.')

        from django.contrib.auth.models import Group as DjangoGroup
        groups = DjangoGroup.objects.filter(id__in=group_ids)
        user.groups.set(groups)
        _sync_staff_for_user(user)
        user = User.objects.select_related('profile').get(pk=user.pk)
        return Response(UserSerializer(user, context={'request': request}).data)

    # ── /{pk}/set_permission_categories ─────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='set_permission_categories')
    def set_permission_categories(self, request, pk=None):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return _err('User not found.', status.HTTP_404_NOT_FOUND)

        cat_ids = request.data.get('category_ids', [])
        if not isinstance(cat_ids, list):
            return _err('category_ids must be a list.')

        from apps.permissions.models import PermissionCategory
        profile, _ = UserProfile.objects.get_or_create(user=user)
        cats = PermissionCategory.objects.filter(id__in=cat_ids)
        profile.permission_categories.set(cats)

        # Sync user_permissions from categories
        perm_ids = set()
        for cat in profile.permission_categories.prefetch_related('permissions').all():
            perm_ids.update(cat.permissions.values_list('id', flat=True))
        user.user_permissions.set(Permission.objects.filter(id__in=perm_ids))

        user = User.objects.select_related('profile').get(pk=user.pk)
        return Response(UserSerializer(user, context={'request': request}).data)

    # ── /ping ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='mention-search')
    def mention_search(self, request):
        """Lightweight search returning id + display_name for @mention autocomplete."""
        q = request.query_params.get('q', '').strip()
        from django.db.models import Q
        qs = User.objects.filter(is_active=True)
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q)
            )
        qs = qs.order_by('first_name', 'last_name')[:15]
        return Response([
            {'id': u.pk, 'display_name': u.get_full_name() or u.email, 'email': u.email}
            for u in qs
        ])

    @action(detail=False, methods=['post'], url_path='ping')
    def ping(self, request):
        """Refresh _rp_last_activity so the session timeout resets."""
        import time
        request.session['_rp_last_activity'] = time.time()
        return Response({'ok': True})

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
# UserGroupViewSet (backed by Django's auth.Group + GroupProfile)
# ---------------------------------------------------------------------------

class UserGroupViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not request.user.is_staff:
            return _err('Admin access required.', status.HTTP_403_FORBIDDEN)
        return None

    def _get_group(self, pk):
        try:
            return Group.objects.select_related('profile').get(pk=pk)
        except Group.DoesNotExist:
            return None

    # ── List ─────────────────────────────────────────────────────────────────
    def list(self, request):
        qs = Group.objects.select_related('profile').all()
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        qs = qs.order_by('name')
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
        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)
        return Response(UserGroupSerializer(group).data)

    # ── Update ────────────────────────────────────────────────────────────────
    def partial_update(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny

        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        try:
            profile = group.profile
            is_system = profile.is_system
        except GroupProfile.DoesNotExist:
            profile = GroupProfile.objects.create(group=group)
            is_system = False

        # System groups: name is protected
        if 'name' in request.data and is_system:
            return _err('System group names cannot be changed.')

        # Update group name
        if 'name' in request.data:
            name = str(request.data['name']).strip()
            if not name:
                return Response(
                    {'error': 'Validation failed.', 'details': {'name': ['Name cannot be blank.']}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if Group.objects.filter(name__iexact=name).exclude(pk=group.pk).exists():
                return Response(
                    {'error': 'Validation failed.', 'details': {'name': ['A group with this name already exists.']}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            group.name = name
            group.save(update_fields=['name'])

        # Update profile description
        profile_changed = []
        if 'description' in request.data:
            profile.description = request.data['description']
            profile_changed.append('description')

        # Update permission categories (blocked for system groups); permissions derived from categories only
        categories_changed = False
        has_cat_data = 'category_ids' in request.data or 'category_assignments' in request.data
        if has_cat_data and not is_system:
            from apps.users.serializers import _apply_category_assignments
            cat_ids     = request.data.get('category_ids', [])
            assignments = request.data.get('category_assignments', [])
            if isinstance(cat_ids, list) or isinstance(assignments, list):
                _apply_category_assignments(profile, group, cat_ids, assignments)
                categories_changed = True

        # Auto-compute is_admin_group from permission coverage (skip for system groups)
        if not is_system and categories_changed:
            new_is_admin = _is_admin_by_coverage(group)
            if profile.is_admin_group != new_is_admin:
                profile.is_admin_group = new_is_admin
                profile_changed.append('is_admin_group')

        if profile_changed:
            profile.save(update_fields=profile_changed)

        # Re-sync staff flag for all members whenever categories changed
        if categories_changed:
            for user in group.user_set.all():
                _sync_staff_for_user(user)

        group.refresh_from_db()
        return Response(UserGroupSerializer(group).data)

    # ── Delete ────────────────────────────────────────────────────────────────
    def destroy(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny

        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        try:
            if group.profile.is_system:
                return _err('System groups cannot be deleted.')
        except GroupProfile.DoesNotExist:
            pass

        members = list(group.user_set.all())
        group.delete()
        for user in members:
            _sync_staff_for_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── /stats ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        total = Group.objects.count()
        admin = GroupProfile.objects.filter(is_admin_group=True).count()
        return Response({'total': total, 'admin': admin})

    # ── /{pk}/members ─────────────────────────────────────────────────────────
    @action(detail=True, methods=['get'], url_path='members')
    def members(self, request, pk=None):
        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        qs = group.user_set.select_related('profile').order_by('email')

        try:
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 25

        paginator = Paginator(qs, page_size)
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

        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list) or not user_ids:
            return _err('user_ids must be a non-empty list.')

        added = []
        for uid in user_ids:
            try:
                user = User.objects.get(pk=uid)
                if not group.user_set.filter(pk=user.pk).exists():
                    group.user_set.add(user)
                    added.append(uid)
                    try:
                        if group.profile.is_admin_group:
                            _sync_staff_for_user(user)
                    except GroupProfile.DoesNotExist:
                        pass
            except User.DoesNotExist:
                pass

        return Response({'added': added, 'member_count': group.user_set.count()})

    # ── /{pk}/remove_members ──────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='remove_members')
    def remove_members(self, request, pk=None):
        deny = self._require_admin(request)
        if deny:
            return deny

        group = self._get_group(pk)
        if group is None:
            return _err('Group not found.', status.HTTP_404_NOT_FOUND)

        user_ids = request.data.get('user_ids', [])
        if not isinstance(user_ids, list) or not user_ids:
            return _err('user_ids must be a non-empty list.')

        removed = []
        for uid in user_ids:
            try:
                user = User.objects.get(pk=uid)
                if group.user_set.filter(pk=user.pk).exists():
                    group.user_set.remove(user)
                    removed.append(uid)
                    _sync_staff_for_user(user)
            except User.DoesNotExist:
                pass

        return Response({'removed': removed, 'member_count': group.user_set.count()})
