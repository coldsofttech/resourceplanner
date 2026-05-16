from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configurations', '0004_alter_value_allow_blank'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='module',
            field=models.CharField(
                choices=[
                    ('general', 'General'),
                    ('integration_ai', 'AI Integration'),
                    ('integration_email', 'Email Integration'),
                    ('integration_sso', 'SSO Integration'),
                    ('integration_jira', 'Jira Integration'),
                    ('security', 'Security'),
                    ('security_password', 'Password Policy'),
                ],
                default='general',
                help_text='Logical grouping: general, integration_*, security, or security_password.',
                max_length=30,
            ),
        ),
    ]
