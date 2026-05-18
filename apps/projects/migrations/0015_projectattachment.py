from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0014_project_completed_sprint'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, default='', max_length=100)),
                ('file_size', models.PositiveBigIntegerField(default=0)),
                ('file_data', models.BinaryField(blank=True, null=True)),
                ('file_path', models.CharField(blank=True, default='', max_length=1000)),
                ('s3_key', models.CharField(blank=True, default='', max_length=1000)),
                ('uploaded_by', models.CharField(default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='projects.project')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
