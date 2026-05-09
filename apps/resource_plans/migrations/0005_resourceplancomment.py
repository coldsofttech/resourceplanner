import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0004_resourceplan_is_head'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ResourcePlanNote',
            new_name='ResourcePlanComment',
        ),
        migrations.RenameField(
            model_name='resourceplancomment',
            old_name='note',
            new_name='comment',
        ),
        migrations.AddField(
            model_name='resourceplancomment',
            name='posted_by',
            field=models.CharField(default='Anonymous', max_length=200),
        ),
        migrations.AlterField(
            model_name='resourceplancomment',
            name='plan',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comments',
                to='resource_plans.resourceplan',
            ),
        ),
    ]
