from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sprint_forecast', '0005_project_actuals'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectactuals',
            name='ignore_risk',
            field=models.BooleanField(
                default=False,
                help_text='When True, this project is excluded from risk calculations and treated as Neutral.',
            ),
        ),
    ]
