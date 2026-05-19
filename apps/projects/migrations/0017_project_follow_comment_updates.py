import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0016_projectestimate_approval_email_sent'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ProjectComment — add posted_by_user FK
        migrations.AddField(
            model_name='projectcomment',
            name='posted_by_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='project_comments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # ProjectComment — add mentioned_users M2M
        migrations.AddField(
            model_name='projectcomment',
            name='mentioned_users',
            field=models.ManyToManyField(
                blank=True,
                related_name='project_comment_mentions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # ProjectCommentAttachment
        migrations.CreateModel(
            name='ProjectCommentAttachment',
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
                    to='projects.projectcomment',
                )),
            ],
            options={'ordering': ['created_at']},
        ),
        # ProjectFollower
        migrations.CreateModel(
            name='ProjectFollower',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='followers',
                    to='projects.project',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='followed_projects',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='projectfollower',
            constraint=models.UniqueConstraint(
                fields=['project', 'user'],
                name='unique_project_follower',
            ),
        ),
    ]
