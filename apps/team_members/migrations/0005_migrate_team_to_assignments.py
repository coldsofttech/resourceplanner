from django.db import migrations


def forward_migrate_team(apps, schema_editor):
    TeamMember = apps.get_model('team_members', 'TeamMember')
    TeamMemberAssignment = apps.get_model('team_members', 'TeamMemberAssignment')
    for member in TeamMember.objects.exclude(team__isnull=True).select_related('team'):
        TeamMemberAssignment.objects.get_or_create(member=member, team=member.team)


def reverse_migrate_team(apps, schema_editor):
    TeamMember = apps.get_model('team_members', 'TeamMember')
    TeamMemberAssignment = apps.get_model('team_members', 'TeamMemberAssignment')
    for assignment in TeamMemberAssignment.objects.select_related('member', 'team'):
        TeamMember.objects.filter(pk=assignment.member_id).update(team=assignment.team)


class Migration(migrations.Migration):

    dependencies = [
        ('team_members', '0004_teammemberassignment'),
    ]

    operations = [
        migrations.RunPython(forward_migrate_team, reverse_migrate_team),
    ]
