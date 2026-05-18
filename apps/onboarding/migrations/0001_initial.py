import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('business_units', '0001_initial'),
        ('projects', '0015_projectattachment'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_name', models.CharField(max_length=200)),
                ('requester_email', models.EmailField()),
                ('accountable_executive_email', models.EmailField(blank=True, default='')),
                ('requirements', models.TextField(blank=True, default='')),
                ('tentative_start_date', models.DateField(blank=True, null=True)),
                ('tentative_end_date', models.DateField(blank=True, null=True)),
                ('project_code', models.CharField(blank=True, default='', max_length=100)),
                ('risk', models.TextField(blank=True, default='')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_from_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('business_unit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='onboarding_requests', to='business_units.businessunit')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='onboarding_requests', to='projects.project')),
            ],
            options={
                'ordering': ['-submitted_at'],
            },
        ),
        migrations.CreateModel(
            name='OnboardingRequestContact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('REQUESTER', 'Requester'), ('POC', 'Point of Contact')], max_length=20)),
                ('email', models.EmailField()),
                ('name', models.CharField(blank=True, default='', max_length=200)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contacts', to='onboarding.onboardingrequest')),
            ],
            options={
                'ordering': ['role', 'email'],
            },
        ),
        migrations.CreateModel(
            name='OnboardingRequestLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=2000)),
                ('title', models.CharField(blank=True, default='', max_length=200)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='links', to='onboarding.onboardingrequest')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='OnboardingRequestAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, default='', max_length=100)),
                ('file_size', models.PositiveBigIntegerField(default=0)),
                ('file_data', models.BinaryField(blank=True, null=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='onboarding.onboardingrequest')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
