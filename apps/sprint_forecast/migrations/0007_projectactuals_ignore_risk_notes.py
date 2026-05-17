from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0006_projectactuals_ignore_risk'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectactuals',
            name='ignore_risk_notes',
            field=models.TextField(
                blank=True,
                help_text='Optional reason for ignoring risk on this project.',
            ),
        ),
    ]
