import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import UserProfile, GroupProfile


def _is_admin_by_coverage(group):
    """True if the group's permissions span every included-app module that has perms in the DB."""
    _INCLUDED_APPS = [
        'delivery_teams', 'team_members', 'member_leaves', 'financial_years',
        'sprints', 'sprint_capacity', 'resource_plans', 'projects', 'programmes',
        'contacts', 'skills', 'team_roles', 'office_locations', 'employment_types',
        'project_types', 'project_sub_statuses', 'public_holidays',
    ]
    modules_with_perms = set(
        Permission.objects
        .filter(content_type__app_label__in=_INCLUDED_APPS)
        .values_list('content_type__app_label', flat=True)
        .distinct()
    )
    if not modules_with_perms:
        return False
    group_modules = set(
        group.permissions
        .filter(content_type__app_label__in=_INCLUDED_APPS)
        .values_list('content_type__app_label', flat=True)
        .distinct()
    )
    return modules_with_perms == group_modules

User = get_user_model()
logger = logging.getLogger(__name__)


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_thumb = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['sso_provider', 'sso_uid', 'avatar_url', 'avatar', 'avatar_thumb', 'timezone', 'theme']
        read_only_fields = ['sso_provider', 'sso_uid']

    def get_avatar_thumb(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            url = obj.avatar.url
            return request.build_absolute_uri(url) if request else url
        return obj.avatar_url or ''


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    avatar_display = serializers.SerializerMethodField()
    group_ids = serializers.SerializerMethodField()
    explicit_category_ids = serializers.SerializerMethodField()
    group_category_ids = serializers.SerializerMethodField()
    effective_permission_ids = serializers.SerializerMethodField()
    group_permission_summary = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login',
            'profile', 'avatar_display',
            'group_ids', 'explicit_category_ids', 'group_category_ids',
            'effective_permission_ids', 'group_permission_summary',
        ]
        read_only_fields = ['date_joined', 'last_login', 'is_superuser']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_avatar_display(self, obj):
        try:
            profile = obj.profile
            if profile.avatar:
                request = self.context.get('request')
                url = profile.avatar.url
                return request.build_absolute_uri(url) if request else url
            return profile.avatar_url or ''
        except UserProfile.DoesNotExist:
            return ''

    def get_group_ids(self, obj):
        return list(obj.groups.values_list('id', flat=True))

    def get_explicit_category_ids(self, obj):
        try:
            return list(obj.profile.permission_categories.values_list('id', flat=True))
        except UserProfile.DoesNotExist:
            return []

    def get_group_category_ids(self, obj):
        """Category IDs inherited via group membership (read-only, not explicitly assigned)."""
        cat_ids = set()
        for group in obj.groups.select_related('profile').all():
            try:
                cat_ids.update(group.profile.permission_categories.values_list('id', flat=True))
            except Exception:
                pass
        return list(cat_ids)

    def get_effective_permission_ids(self, obj):
        """Union of permissions from explicit categories + all group permissions."""
        perm_ids = set()
        # From explicit user categories
        try:
            for cat in obj.profile.permission_categories.prefetch_related('permissions').all():
                perm_ids.update(cat.permissions.values_list('id', flat=True))
        except UserProfile.DoesNotExist:
            pass
        # From groups
        for group in obj.groups.prefetch_related('permissions').all():
            perm_ids.update(group.permissions.values_list('id', flat=True))
        return list(perm_ids)

    def get_group_permission_summary(self, obj):
        """Per-group list of category IDs that contribute to this user's permissions."""
        result = []
        for group in obj.groups.select_related('profile').all():
            try:
                cat_ids = list(group.profile.permission_categories.values_list('id', flat=True))
            except Exception:
                cat_ids = []
            result.append({'group_id': group.id, 'group_name': group.name, 'category_ids': cat_ids})
        return result


class UserCreateSerializer(serializers.Serializer):
    """Creates a user without a password; an invitation email is sent instead."""
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, default='')
    email = serializers.EmailField()

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def create(self, validated_data):
        import secrets as _secrets
        email = validated_data['email']
        username = email[:150]
        if User.objects.filter(username=username).exists():
            username = f'{email[:140]}{_secrets.token_hex(4)}'
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', ''),
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'must_change_password': True},
        )
        return user


class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)

    def update(self, instance, validated_data):
        for field in ('first_name', 'last_name', 'is_staff', 'is_active'):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# UserGroup (using Django's built-in auth.Group + GroupProfile)
# ---------------------------------------------------------------------------

class UserGroupMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_display = serializers.SerializerMethodField()
    joined_at = serializers.SerializerMethodField()
    is_default_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name',
                  'is_active', 'is_staff', 'avatar_display', 'joined_at', 'is_default_admin']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_avatar_display(self, obj):
        try:
            p = obj.profile
            if p.avatar:
                req = self.context.get('request')
                url = p.avatar.url
                return req.build_absolute_uri(url) if req else url
            return p.avatar_url or ''
        except Exception:
            return ''

    def get_joined_at(self, obj):
        # Django's auth.Group M2M has no timestamp
        return None

    def get_is_default_admin(self, obj):
        from apps.users.apps import DEFAULT_ADMIN_EMAIL
        return obj.email.lower() == DEFAULT_ADMIN_EMAIL.lower()


class UserGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    is_admin_group = serializers.SerializerMethodField()
    is_system = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    permission_ids = serializers.SerializerMethodField()
    category_ids = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'is_admin_group', 'is_system',
            'member_count', 'permission_ids', 'category_ids', 'created_at', 'updated_at',
        ]

    def get_member_count(self, obj):
        return obj.user_set.count()

    def get_is_admin_group(self, obj):
        try:
            return obj.profile.is_admin_group
        except Exception:
            return False

    def get_is_system(self, obj):
        try:
            return obj.profile.is_system
        except Exception:
            return False

    def get_description(self, obj):
        try:
            return obj.profile.description
        except Exception:
            return ''

    def get_created_at(self, obj):
        try:
            return obj.profile.created_at.isoformat()
        except Exception:
            return None

    def get_updated_at(self, obj):
        try:
            return obj.profile.updated_at.isoformat()
        except Exception:
            return None

    def get_permission_ids(self, obj):
        return list(obj.permissions.values_list('id', flat=True))

    def get_category_ids(self, obj):
        try:
            return list(obj.profile.permission_categories.values_list('id', flat=True))
        except Exception:
            return []

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Name cannot be blank.')
        qs = Group.objects.filter(name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A group with this name already exists.')
        return name


class UserGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    category_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Name cannot be blank.')
        if Group.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError('A group with this name already exists.')
        return name

    def create(self, validated_data):
        from apps.permissions.models import PermissionCategory
        cat_ids = validated_data.pop('category_ids', [])
        group = Group.objects.create(name=validated_data['name'])
        profile = GroupProfile.objects.create(
            group=group,
            description=validated_data.get('description', ''),
            is_admin_group=False,
            is_system=False,
        )
        if cat_ids:
            cats = PermissionCategory.objects.filter(id__in=cat_ids)
            profile.permission_categories.set(cats)
            perm_ids = set()
            for cat in cats:
                perm_ids.update(cat.permissions.values_list('id', flat=True))
            if perm_ids:
                group.permissions.set(Permission.objects.filter(id__in=perm_ids))
        # Auto-compute is_admin_group: admin if perms span all available modules
        profile.is_admin_group = _is_admin_by_coverage(group)
        profile.save(update_fields=['is_admin_group'])
        return group
