import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resource_plans', '0021_audit_log'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='resourceplancomment',
            name='posted_by_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='resource_plan_comments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='resourceplancomment',
            name='mentioned_users',
            field=models.ManyToManyField(
                blank=True,
                related_name='resource_plan_comment_mentions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='ResourcePlanCommentAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name',    models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, default='', max_length=100)),
                ('file_size',    models.PositiveBigIntegerField(default=0)),
                ('file_data',    models.BinaryField(blank=True, null=True)),
                ('file_path',    models.CharField(blank=True, default='', max_length=1000)),
                ('s3_key',       models.CharField(blank=True, default='', max_length=1000)),
                ('uploaded_by',  models.CharField(default='', max_length=200)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('comment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='resource_plans.resourceplancomment',
                )),
            ],
            options={'ordering': ['created_at']},
        ),
    ]
