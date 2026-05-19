from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_teams', '0001_initial'),
        ('team_members', '0005_migrate_team_to_assignments'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teammember',
            name='team',
        ),
    ]
