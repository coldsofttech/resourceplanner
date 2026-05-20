from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_notification_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('comment_mention',     'Comment Mention'),
                    ('project_approved',    'Project Approved'),
                    ('recharge_forecast',   'Recharge Forecast'),
                    ('recharge_actuals',    'Recharge Actuals'),
                    ('project_follow',      'Project Update'),
                    ('monthly_wins_phase1', 'Monthly Wins Phase 1'),
                    ('monthly_wins_phase2', 'Monthly Wins Phase 2'),
                    ('todo_mention',        'To-Do Mention'),
                    ('todo_assigned',       'To-Do Assigned'),
                    ('todo_reminder',       'To-Do Reminder'),
                ],
                max_length=50,
            ),
        ),
    ]
