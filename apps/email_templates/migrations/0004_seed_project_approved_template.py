from django.db import migrations

_SUBJECT = 'Project Approved: {{ project_name }} [{{ project_code }}]'

_BODY = """\
<p>Hi all,</p>

<p>The estimate for project <strong>{{ project_name }}</strong> has been approved and the project is now <strong>In Progress</strong>.</p>

<table style="width:100%;border-collapse:collapse;margin:16px 0">
  <tr>
    <td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:600;width:180px;background:#f8f9fa">Project Name</td>
    <td style="padding:6px 12px;border:1px solid #dee2e6">{{ project_name }}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:600;background:#f8f9fa">Programme</td>
    <td style="padding:6px 12px;border:1px solid #dee2e6">{{ programme_name }}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:600;background:#f8f9fa">Project Code</td>
    <td style="padding:6px 12px;border:1px solid #dee2e6">{{ project_code }}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:600;background:#f8f9fa">Label</td>
    <td style="padding:6px 12px;border:1px solid #dee2e6">{{ project_label }}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;border:1px solid #dee2e6;font-weight:600;background:#f8f9fa">Approved Estimate</td>
    <td style="padding:6px 12px;border:1px solid #dee2e6"><a href="{{ estimate_link }}">View Estimate</a></td>
  </tr>
</table>

<p><strong>Run Cost:</strong> {{ run_cost_message }}.</p>

{{ recharge_contacts }}

<p>
  <strong>Assigned Team:</strong> {{ assigned_team_mentions }}<br>
  <strong>Collaborators:</strong> {{ collaborator_mentions }}<br>
  <strong>Info Contacts:</strong> {{ info_contact_mentions }}<br>
  <strong>FinOps Contacts:</strong> {{ finops_contact_mentions }}
</p>

<p>Kind regards,<br><strong>{{ app_name }}</strong></p>
"""


def _seed(apps, schema_editor):
    EmailTemplate = apps.get_model('email_templates', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        scenario='project_approved',
        defaults={'subject': _SUBJECT, 'body': _BODY, 'is_active': True},
    )


def _reverse(apps, schema_editor):
    EmailTemplate = apps.get_model('email_templates', 'EmailTemplate')
    EmailTemplate.objects.filter(scenario='project_approved', subject=_SUBJECT).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('email_templates', '0003_alter_emailtemplate_scenario'),
    ]

    operations = [
        migrations.RunPython(_seed, _reverse),
    ]
