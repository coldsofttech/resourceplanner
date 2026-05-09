from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0003_remove_resourceplan_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourceplan',
            name='is_head',
            field=models.BooleanField(default=True),
        ),
    ]
