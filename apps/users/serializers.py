import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import UserProfile, UserGroup, UserGroupMembership

User = get_user_model()
logger = logging.getLogger(__name__)


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_thumb = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['sso_provider', 'sso_uid', 'avatar_url', 'avatar', 'avatar_thumb']
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

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login',
            'profile', 'avatar_display',
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


class UserCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, default='')
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    is_staff = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return email

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        import secrets as _secrets
        email = validated_data['email']
        username = email[:150]
        if User.objects.filter(username=username).exists():
            username = f'{email[:140]}{_secrets.token_hex(4)}'
        return User.objects.create_user(
            username=username,
            email=email,
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password'],
            is_staff=validated_data.get('is_staff', False),
        )


class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._instance = instance

    def validate_email(self, value):
        email = value.lower().strip()
        qs = User.objects.filter(email__iexact=email)
        if self._instance:
            qs = qs.exclude(pk=self._instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Another account is using this email.')
        return email

    def update(self, instance, validated_data):
        for field in ('first_name', 'last_name', 'is_staff', 'is_active'):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        if 'email' in validated_data:
            new_email = validated_data['email']
            instance.email = new_email
            instance.username = new_email[:150]
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# UserGroup
# ---------------------------------------------------------------------------

class UserGroupMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_display = serializers.SerializerMethodField()
    joined_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name',
                  'is_active', 'is_staff', 'avatar_display', 'joined_at']

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
        # Injected via annotate in viewset
        membership = getattr(obj, '_membership', None)
        if membership:
            return membership.joined_at.isoformat()
        return None


class UserGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = UserGroup
        fields = [
            'id', 'name', 'description', 'is_admin_group', 'is_system',
            'member_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['is_system', 'created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.members.count()

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Name cannot be blank.')
        qs = UserGroup.objects.filter(name__iexact=name)
        instance = self.instance
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A group with this name already exists.')
        return name


class UserGroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, default='', allow_blank=True)
    is_admin_group = serializers.BooleanField(required=False, default=False)

    def validate_name(self, value):
        name = value.strip()
        if UserGroup.objects.filter(name__iexact=name).exists():
            raise serializers.ValidationError('A group with this name already exists.')
        return name

    def create(self, validated_data):
        return UserGroup.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            is_admin_group=validated_data.get('is_admin_group', False),
            is_system=False,
        )
