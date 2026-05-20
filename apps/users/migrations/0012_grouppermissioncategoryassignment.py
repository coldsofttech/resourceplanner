from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_assignments(apps, schema_editor):
    """Copy existing group-category M2M rows into the new through model."""
    db = schema_editor.connection.alias
    GroupProfile = apps.get_model('users', 'GroupProfile')
    GroupPermissionCategoryAssignment = apps.get_model('users', 'GroupPermissionCategoryAssignment')

    for profile in GroupProfile.objects.using(db).prefetch_related('permission_categories'):
        for cat in profile.permission_categories.using(db).all():
            GroupPermissionCategoryAssignment.objects.using(db).get_or_create(
                group=profile, category=cat, defaults={'scope_override': ''}
            )


class Migration(migrations.Migration):

    dependencies = [
        ('permissions', '0003_permissioncategory_scope'),
        ('users', '0011_userprofileavatar'),
    ]

    operations = [
        # Step 1: create the through-model table
        migrations.CreateModel(
            name='GroupPermissionCategoryAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope_override', models.CharField(
                    blank=True,
                    choices=[
                        ('', 'Use category default'),
                        ('all', 'All — no restriction'),
                        ('team', 'Team — own delivery team only'),
                        ('self', 'Self — own records only'),
                    ],
                    default='',
                    help_text='Override the category scope for this group. Blank = use category default.',
                    max_length=10,
                )),
                ('category', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='group_assignments',
                    to='permissions.permissioncategory',
                )),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='category_assignments',
                    to='users.groupprofile',
                )),
            ],
            options={
                'unique_together': {('group', 'category')},
            },
        ),
        # Step 2: copy existing M2M data into the through model (old junction table still exists here)
        migrations.RunPython(migrate_existing_assignments, migrations.RunPython.noop),
        # Step 3: drop the old implicit junction table
        migrations.RemoveField(
            model_name='groupprofile',
            name='permission_categories',
        ),
        # Step 4: add the new M2M field pointing at the through model (no new table created)
        migrations.AddField(
            model_name='groupprofile',
            name='permission_categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='groups',
                through='users.GroupPermissionCategoryAssignment',
                to='permissions.permissioncategory',
            ),
        ),
    ]
