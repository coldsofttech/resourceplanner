import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def link_existing_users(apps, schema_editor):
    """
    Populate TeamMember.user for any existing records where email_address
    matches a User's email (case-insensitive). First match wins; duplicates
    are skipped with a warning in the migration output.
    """
    TeamMember = apps.get_model('team_members', 'TeamMember')
    User       = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0],
                                settings.AUTH_USER_MODEL.split('.')[1])

    linked = 0
    skipped = 0
    for member in TeamMember.objects.filter(user__isnull=True):
        try:
            user = User.objects.get(email__iexact=member.email_address)
            # Check no other member already claimed this user
            if not TeamMember.objects.filter(user=user).exists():
                member.user = user
                member.save(update_fields=['user'])
                linked += 1
            else:
                skipped += 1
        except User.DoesNotExist:
            pass
        except User.MultipleObjectsReturned:
            skipped += 1

    print(f'\n  Linked {linked} team member(s) to user accounts. '
          f'{skipped} skipped (no match or duplicate email).')


def unlink_users(apps, schema_editor):
    TeamMember = apps.get_model('team_members', 'TeamMember')
    TeamMember.objects.filter(user__isnull=False).update(user=None)


class Migration(migrations.Migration):

    dependencies = [
        ('team_members', '0002_alter_teammember_default_holidays'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='teammember',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='team_member',
                to=settings.AUTH_USER_MODEL,
                help_text=(
                    "Linked login account. Auto-populated by matching email_address "
                    "to the user's email. Cleared automatically if the user is deleted."
                ),
            ),
        ),
        migrations.RunPython(link_existing_users, reverse_code=unlink_users),
    ]
