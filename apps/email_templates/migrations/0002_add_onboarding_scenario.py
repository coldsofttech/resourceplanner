from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('email_templates', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtemplate',
            name='scenario',
            field=models.CharField(
                choices=[
                    ('user_created', 'New User Created'),
                    ('password_reset', 'Password Reset'),
                    ('recharge_forecast', 'Recharge Forecast'),
                    ('recharge_actuals', 'Recharge Actuals'),
                    ('onboarding_submitted', 'Onboarding Submitted'),
                ],
                max_length=50,
                unique=True,
            ),
        ),
    ]
