from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('delivery_teams', '__first__'),
        ('team_members', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrgChartNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('job_title', models.CharField(blank=True, max_length=200)),
                ('email', models.CharField(blank=True, max_length=254)),
                ('avatar_url', models.CharField(blank=True, max_length=500)),
                ('is_vacant', models.BooleanField(default=False)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('team', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='orgchart_nodes',
                    to='delivery_teams.deliveryteam',
                )),
                ('parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='children',
                    to='orgchart.orgchartnode',
                )),
                ('team_member', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='orgchart_nodes',
                    to='team_members.teammember',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='orgchart_nodes_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
    ]
