from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Todo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=500)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('done', 'Done')],
                    default='open', max_length=20,
                )),
                ('priority', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
                    default='medium', max_length=10,
                )),
                ('due_date', models.DateField(blank=True, null=True)),
                ('reminder_at', models.DateTimeField(blank=True, null=True)),
                ('reminder_sent', models.BooleanField(default=False)),
                ('is_recurring', models.BooleanField(default=False)),
                ('recurrence_rule', models.CharField(
                    blank=True,
                    choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly')],
                    max_length=10,
                )),
                ('recurrence_interval', models.PositiveIntegerField(default=1)),
                ('recurrence_end_date', models.DateField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='todos_assigned',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='todos_created',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('parent_todo', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurrence_children',
                    to='todos.todo',
                )),
            ],
            options={
                'ordering': ['status', 'due_date', '-priority', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TodoComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('todo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to='todos.todo',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='todo_comments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
