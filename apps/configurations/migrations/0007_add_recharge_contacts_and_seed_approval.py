from django.db import migrations, models

_APPROVAL_CONFIGS = [
    {
        'code': 'PROJECT_APPROVAL_NOTIFY_ROLES',
        'label': 'Notify Roles (Assigned & Collaborator Teams)',
        'value': '',
        'description': 'Comma-separated TeamRole PKs. Members of the assigned team and collaborator teams holding these roles will receive the approval email.',
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'PROJECT_APPROVAL_INFO_CONTACTS',
        'label': 'Informational Contacts',
        'value': '',
        'description': 'Comma-separated Contact PKs. These contacts receive the email for informational purposes only.',
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'PROJECT_APPROVAL_FINOPS_CONTACTS',
        'label': 'FinOps Contacts',
        'value': '',
        'description': 'Comma-separated Contact PKs for FinOps recipients who receive run-cost details.',
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'PROJECT_APPROVAL_CHARGE_TYPES',
        'label': 'Run Cost — Charge It Project Types',
        'value': '',
        'description': "Comma-separated ProjectType PKs. Projects of these types produce the 'run cost applies and charge it' message.",
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'PROJECT_APPROVAL_NO_CHARGE_TYPES',
        'label': 'Run Cost — Do Not Charge Project Types',
        'value': '',
        'description': "Comma-separated ProjectType PKs. Projects of these types produce the 'run cost applies but do not charge it' message.",
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES',
        'label': 'Recharge Contact Roles (listed in email body)',
        'value': '',
        'description': 'Comma-separated TeamRole PKs. Assigned team members holding these roles are listed as recharge contacts in the email body.',
        'data_type': 'string',
        'is_secret': False,
        'module': 'project_approval',
    },
    {
        'code': 'RECHARGE_CC_CONTACTS',
        'label': 'Recharge Email CC Contacts',
        'value': '',
        'description': 'Comma-separated Contact PKs. These contacts are CC\'d on every Sprint Forecast and Sprint Actuals recharge email.',
        'data_type': 'string',
        'is_secret': False,
        'module': 'recharge_contacts',
    },
]


def _seed(apps, schema_editor):
    Configuration = apps.get_model('configurations', 'Configuration')
    for cfg in _APPROVAL_CONFIGS:
        Configuration.objects.get_or_create(code=cfg['code'], defaults=cfg)


def _reverse(apps, schema_editor):
    Configuration = apps.get_model('configurations', 'Configuration')
    for cfg in _APPROVAL_CONFIGS:
        Configuration.objects.filter(code=cfg['code']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configurations', '0006_alter_configuration_module'),
    ]

    operations = [
        migrations.AlterField(
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
                    ('project_approval', 'Project Approval'),
                    ('recharge_contacts', 'Recharge Contacts'),
                ],
                default='general',
                help_text='Logical grouping: general, integration_*, security, security_password, project_approval, or recharge_contacts.',
                max_length=30,
            ),
        ),
        migrations.RunPython(_seed, _reverse),
    ]
