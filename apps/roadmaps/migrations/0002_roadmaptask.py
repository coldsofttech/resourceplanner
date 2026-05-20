import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roadmaps', '0001_initial'),
        ('sprints', '0002_sprint_closed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RoadmapTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_type', models.CharField(choices=[('task', 'Task'), ('milestone', 'Milestone')], default='task', max_length=20)),
                ('name', models.CharField(max_length=200)),
                ('jira_id', models.CharField(blank=True, default='', max_length=50)),
                ('is_blocker', models.BooleanField(default=False)),
                ('is_complete', models.BooleanField(default=False)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('roadmap_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='roadmaps.roadmapitem')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='roadmap_tasks', to=settings.AUTH_USER_MODEL)),
                ('start_sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rm_tasks_start', to='sprints.sprint')),
                ('end_sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rm_tasks_end', to='sprints.sprint')),
            ],
            options={
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
