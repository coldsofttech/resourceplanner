import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_titles(apps, schema_editor):
    WinEntry = apps.get_model('wins', 'WinEntry')
    for entry in WinEntry.objects.all():
        first_line = (entry.description or '').split('\n')[0][:200].strip()
        entry.title = first_line or 'Win entry'
        entry.save(update_fields=['title'])


class Migration(migrations.Migration):

    dependencies = [
        ('wins', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename content → description on WinEntry
        migrations.RenameField(
            model_name='winentry',
            old_name='content',
            new_name='description',
        ),
        # Add title with a temporary default so existing rows can get a value
        migrations.AddField(
            model_name='winentry',
            name='title',
            field=models.CharField(max_length=200, default=''),
            preserve_default=False,
        ),
        # Populate title from first line of description
        migrations.RunPython(populate_titles, reverse_code=migrations.RunPython.noop),
        # Add status to Win
        migrations.AddField(
            model_name='win',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('open', 'Open'), ('review_complete', 'Review Complete')],
                default='open',
            ),
        ),
        migrations.AddField(
            model_name='win',
            name='reviewed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='win',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='wins_reviewed',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
