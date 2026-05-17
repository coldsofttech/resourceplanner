import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0013_projectview'),
        ('sprints', '0002_sprint_closed'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='completed_sprint',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='completed_projects',
                to='sprints.sprint',
            ),
        ),
    ]
