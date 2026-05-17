from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0007_projectactuals_ignore_risk_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectactuals',
            name='ignore_previous_fy_cost',
            field=models.BooleanField(
                default=False,
                help_text='When True, only the active FY cost is used for risk and remaining calculations.',
            ),
        ),
    ]
