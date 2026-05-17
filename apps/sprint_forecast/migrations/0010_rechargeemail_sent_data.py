from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0009_recharge_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='rechargeemail',
            name='sent_data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
