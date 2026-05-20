from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0005_wins_reports'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('data_source', models.CharField(blank=True, max_length=100)),
                ('visualization', models.CharField(
                    choices=[
                        ('table', 'Table'), ('pivot', 'Pivot'), ('bar', 'Bar Chart'),
                        ('stacked_bar', 'Stacked Bar Chart'), ('pie', 'Pie Chart'),
                        ('line', 'Line Chart'), ('heatmap', 'Heatmap'),
                    ],
                    default='table', max_length=20,
                )),
                ('config', models.JSONField(blank=True, default=dict)),
                ('is_shared', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='owned_custom_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_custom_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='updated_custom_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='CustomReportShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('permission', models.CharField(
                    choices=[('view', 'View'), ('edit', 'Edit')],
                    default='view', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('report', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shares',
                    to='reporting.customreport',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='custom_report_shares',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('shared_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='shared_custom_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='customreportshare',
            constraint=models.UniqueConstraint(
                fields=['report', 'user'],
                name='unique_custom_report_share',
            ),
        ),
    ]
