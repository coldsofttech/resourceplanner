from django.contrib import admin
from .models import EmailTemplate, EmailTemplateHeader, EmailTemplateFooter

admin.site.register(EmailTemplateHeader)
admin.site.register(EmailTemplateFooter)
admin.site.register(EmailTemplate)
