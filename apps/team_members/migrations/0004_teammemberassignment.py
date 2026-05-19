from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_teams', '0001_initial'),
        ('team_members', '0003_teammember_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamMemberAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('member', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='team_assignments',
                    to='team_members.teammember',
                )),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='member_assignments',
                    to='delivery_teams.deliveryteam',
                )),
            ],
            options={
                'ordering': ['team__name'],
                'unique_together': {('member', 'team')},
            },
        ),
    ]
