from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0002_permissioncategory_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='permissioncategory',
            name='scope',
            field=models.CharField(
                choices=[
                    ('all', 'All — no restriction'),
                    ('team', 'Team — own delivery team only'),
                    ('self', 'Self — own records only'),
                ],
                default='all',
                help_text='Data scope this category grants: all records, team records, or own records only.',
                max_length=10,
            ),
        ),
    ]
