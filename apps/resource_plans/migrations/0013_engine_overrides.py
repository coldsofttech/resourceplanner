from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0012_member_capacity_and_steps_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourceplanversion',
            name='has_pl_overrides',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='planenginejob',
            name='remove_overrides',
            field=models.BooleanField(default=False),
        ),
    ]
