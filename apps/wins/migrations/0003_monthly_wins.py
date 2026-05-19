import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_teams', '0002_deliveryteam_member_count'),
        ('wins', '0002_winentry_title_description_win_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # TeamProductOwner
        migrations.CreateModel(
            name='TeamProductOwner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='product_owners',
                    to='delivery_teams.deliveryteam',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='product_owner_teams',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['team__name', 'user__email'],
                'unique_together': {('team', 'user')},
            },
        ),
        # MonthlyWin
        migrations.CreateModel(
            name='MonthlyWin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('draft', 'Draft'),
                        ('phase1_open', 'Phase 1 — Surveys Open'),
                        ('phase1_complete', 'Phase 1 Complete'),
                        ('phase2_open', 'Phase 2 — Surveys Open'),
                        ('declared', 'Winners Declared'),
                    ],
                    default='draft',
                )),
                ('phase1_deadline', models.DateTimeField(null=True, blank=True)),
                ('phase2_deadline', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('wins', models.ManyToManyField(blank=True, related_name='monthly_wins', to='wins.win')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monthly_wins_created',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        # MonthlyWinSurvey
        migrations.CreateModel(
            name='MonthlyWinSurvey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phase', models.CharField(max_length=10, choices=[('phase1', 'Phase 1'), ('phase2', 'Phase 2')])),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ('status', models.CharField(
                    max_length=15,
                    choices=[('pending', 'Pending'), ('completed', 'Completed'), ('overridden', 'Overridden')],
                    default='pending',
                )),
                ('sent_at', models.DateTimeField(null=True, blank=True)),
                ('reminder_count', models.PositiveIntegerField(default=0)),
                ('last_reminder_at', models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('monthly_win', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='surveys',
                    to='wins.monthlywin',
                )),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monthly_win_surveys',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('teams', models.ManyToManyField(
                    blank=True,
                    related_name='monthly_win_surveys',
                    to='delivery_teams.deliveryteam',
                )),
            ],
            options={
                'ordering': ['recipient__email'],
            },
        ),
        # MonthlyWinSurveyNomination
        migrations.CreateModel(
            name='MonthlyWinSurveyNomination',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=25, choices=[
                    ('delivery', 'Delivery'),
                    ('operational_excellence', 'Operational Excellence'),
                ])),
                ('is_dismissed', models.BooleanField(default=False)),
                ('dismissed_reason', models.CharField(max_length=300, blank=True)),
                ('nominated_at', models.DateTimeField(auto_now_add=True)),
                ('entry', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nominations',
                    to='wins.winentry',
                )),
                ('survey', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nominations',
                    to='wins.monthlywinsurvey',
                )),
            ],
            options={
                'ordering': ['category', 'entry__team__name'],
                'unique_together': {('survey', 'entry', 'category')},
            },
        ),
        # MonthlyWinResult
        migrations.CreateModel(
            name='MonthlyWinResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=25, choices=[
                    ('delivery', 'Delivery'),
                    ('operational_excellence', 'Operational Excellence'),
                ])),
                ('rank', models.PositiveIntegerField()),
                ('vote_count', models.PositiveIntegerField(default=0)),
                ('entry', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monthly_results',
                    to='wins.winentry',
                )),
                ('monthly_win', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='results',
                    to='wins.monthlywin',
                )),
            ],
            options={
                'ordering': ['category', 'rank'],
                'unique_together': {('monthly_win', 'category', 'rank')},
            },
        ),
    ]
