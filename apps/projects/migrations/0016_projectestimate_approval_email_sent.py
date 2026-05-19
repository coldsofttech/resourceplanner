from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0015_projectattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectestimate',
            name='approval_email_sent',
            field=models.BooleanField(default=False),
        ),
    ]
