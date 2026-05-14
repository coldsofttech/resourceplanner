from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configurations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuration',
            name='data_type',
            field=models.CharField(
                choices=[
                    ('string', 'String'),
                    ('integer', 'Integer'),
                    ('float', 'Float'),
                    ('boolean', 'Boolean'),
                ],
                default='string',
                help_text='Expected data type of the stored value.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='configuration',
            name='is_secret',
            field=models.BooleanField(
                default=False,
                help_text='If true, the value is treated as a secret and stored encrypted.',
            ),
        ),
    ]
