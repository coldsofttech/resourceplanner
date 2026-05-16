from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='permissioncategory',
            name='module',
            field=models.CharField(
                blank=True,
                choices=[
                    ('delivery_teams', 'Delivery Teams'),
                    ('team_members', 'Team Members'),
                    ('member_leaves', 'Member Leaves'),
                    ('financial_years', 'Financial Years'),
                    ('sprints', 'Sprints'),
                    ('sprint_capacity', 'Sprint Capacity'),
                    ('resource_plans', 'Resource Plans'),
                    ('projects', 'Projects'),
                    ('programmes', 'Programmes'),
                    ('contacts', 'Contacts'),
                    ('skills', 'Skills'),
                    ('team_roles', 'Team Roles'),
                    ('office_locations', 'Office Locations'),
                    ('employment_types', 'Employment Types'),
                    ('project_types', 'Project Types'),
                    ('project_sub_statuses', 'Project Sub-Statuses'),
                    ('public_holidays', 'Public Holidays'),
                ],
                default='',
                help_text='Application module this category belongs to.',
                max_length=50,
            ),
        ),
    ]
