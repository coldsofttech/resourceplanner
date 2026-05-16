from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0002_permissioncategory_module'),
        ('users', '0007_groupprofile_permission_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='permission_categories',
            field=models.ManyToManyField(
                blank=True,
                help_text='Permission categories assigned directly to this user.',
                related_name='user_profiles',
                to='permissions.permissioncategory',
            ),
        ),
    ]
