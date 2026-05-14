from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'sso_provider', 'sso_uid')
    list_filter = ('sso_provider',)
    search_fields = ('user__username', 'user__email', 'sso_uid')
    raw_id_fields = ('user',)
