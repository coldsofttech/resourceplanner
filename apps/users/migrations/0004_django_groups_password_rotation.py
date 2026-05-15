import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_usergroup_must_change_password'),
        ('auth', '0001_initial'),
    ]

    operations = [
        # Remove the M2M field before deleting the through model
        migrations.RemoveField(
            model_name='usergroup',
            name='members',
        ),
        # Drop the through model table
        migrations.DeleteModel(
            name='UserGroupMembership',
        ),
        # Drop the custom UserGroup table
        migrations.DeleteModel(
            name='UserGroup',
        ),
        # Create GroupProfile that wraps Django's auth.Group
        migrations.CreateModel(
            name='GroupProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to='auth.group',
                )),
                ('description', models.TextField(blank=True, default='')),
                ('is_admin_group', models.BooleanField(
                    default=False,
                    help_text='Members of admin groups receive staff-level access across the application.',
                )),
                ('is_system', models.BooleanField(
                    default=False,
                    help_text='System groups are created automatically and cannot be deleted.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['group__name'],
            },
        ),
        # Add password rotation tracking to UserProfile
        migrations.AddField(
            model_name='userprofile',
            name='password_last_changed',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
