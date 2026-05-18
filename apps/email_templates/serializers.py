from rest_framework import serializers

from .models import EmailTemplate, EmailTemplateHeader, EmailTemplateFooter


class EmailTemplateHeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateHeader
        fields = ['id', 'name', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailTemplateFooterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateFooter
        fields = ['id', 'name', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmailTemplateSerializer(serializers.ModelSerializer):
    header_id = serializers.PrimaryKeyRelatedField(
        source='header',
        queryset=EmailTemplateHeader.objects.all(),
        allow_null=True,
        required=False,
    )
    footer_id = serializers.PrimaryKeyRelatedField(
        source='footer',
        queryset=EmailTemplateFooter.objects.all(),
        allow_null=True,
        required=False,
    )
    header_name = serializers.SerializerMethodField()
    footer_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'scenario', 'subject', 'body',
            'header_id', 'footer_id', 'header_name', 'footer_name',
            'table_config', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'scenario', 'created_at', 'updated_at']

    def get_header_name(self, obj):
        return obj.header.name if obj.header else None

    def get_footer_name(self, obj):
        return obj.footer.name if obj.footer else None
