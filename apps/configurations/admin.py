from django.contrib import admin, messages

from .models import Configuration
from .services import ConfigurationService


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ['code', 'label', 'value', 'description', 'created_at', 'updated_at']
    search_fields = ['code', 'label', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['code']
    actions = ['reset_to_defaults']

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    @admin.action(description='Reset selected configurations to factory defaults')
    def reset_to_defaults(self, request, queryset):
        reset_count = 0
        skipped = []
        for config in queryset:
            try:
                ConfigurationService.reset_to_default(config.pk)
                reset_count += 1
            except Exception:
                skipped.append(config.code)

        if reset_count:
            self.message_user(
                request,
                f'{reset_count} configuration(s) reset to factory defaults.',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'No factory default registered for: {", ".join(skipped)}.',
                messages.WARNING,
            )
