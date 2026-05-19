from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_roles', '0002_teamrole_is_assignable_teamrole_is_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='teamrole',
            name='is_shareable',
            field=models.BooleanField(
                default=False,
                help_text='Marks this role as shareable across multiple teams simultaneously (e.g. Scrum Master, Product Owner).',
            ),
        ),
    ]
