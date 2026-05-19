import logging
from html import escape

from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

_RUN_COST_NO_COST = 'no_cost'
_RUN_COST_NO_CHARGE = 'no_charge'
_RUN_COST_CHARGE = 'charge'

_RUN_COST_MESSAGES = {
    _RUN_COST_NO_COST: 'no run cost applies',
    _RUN_COST_NO_CHARGE: 'run cost applies but do not charge it',
    _RUN_COST_CHARGE: 'run cost applies and charge it',
}


class ProjectApprovalEmailService:

    @classmethod
    def send(cls, project, estimate):
        from apps.email_templates.models import EmailTemplate, SCENARIO_PROJECT_APPROVED
        from apps.configurations.services import ConfigurationService

        template = EmailTemplate.objects.filter(
            scenario=SCENARIO_PROJECT_APPROVED, is_active=True
        ).first()
        if not template:
            logger.warning(
                "No active project_approved email template — skipping approval email "
                "for project %s", project.pk
            )
            return

        notify_role_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_NOTIFY_ROLES'))
        info_contact_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_INFO_CONTACTS'))
        finops_contact_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_FINOPS_CONTACTS'))
        charge_type_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_CHARGE_TYPES'))
        no_charge_type_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_NO_CHARGE_TYPES'))
        recharge_role_ids = cls._parse_ids(ConfigurationService.get_str('PROJECT_APPROVAL_RECHARGE_CONTACT_ROLES'))

        team_members = cls._get_team_members(project.assigned_team_id, notify_role_ids) if project.assigned_team_id else []
        collab_members = cls._get_collab_members(project, notify_role_ids)
        info_contacts = cls._get_contacts(info_contact_ids)
        finops_contacts = cls._get_contacts(finops_contact_ids)

        all_emails = cls._collect_emails(team_members, collab_members, info_contacts, finops_contacts)
        if not all_emails:
            logger.warning(
                "No recipient emails found for project approval email — project %s", project.pk
            )
            return

        run_cost_scenario = cls._get_run_cost_scenario(project, charge_type_ids, no_charge_type_ids)

        recharge_contacts_html = ''
        if run_cost_scenario == _RUN_COST_CHARGE and recharge_role_ids:
            recharge_contacts_html = cls._build_recharge_contacts_html(project, recharge_role_ids)

        variables = cls._build_variables(
            project=project,
            estimate=estimate,
            team_members=team_members,
            collab_members=collab_members,
            info_contacts=info_contacts,
            finops_contacts=finops_contacts,
            run_cost_scenario=run_cost_scenario,
            recharge_contacts_html=recharge_contacts_html,
            app_name=ConfigurationService.get_str('APP_NAME', 'ResourcePlanner'),
        )

        subject = cls._substitute(template.subject, variables)
        body = cls._substitute(template.body, variables)

        parts = []
        if template.header:
            parts.append(template.header.content)
        parts.append(body)
        if template.footer:
            parts.append(template.footer.content)
        full_body = '\n'.join(parts)

        from_email = ConfigurationService.get_str('EMAIL_FROM', '') or None
        try:
            msg = EmailMessage(
                subject=subject,
                body=full_body,
                from_email=from_email,
                to=list(all_emails),
            )
            msg.content_subtype = 'html'
            msg.send()
            logger.info(
                "Project approval email sent for project %s to %d recipients",
                project.pk, len(all_emails)
            )
        except Exception as exc:
            logger.exception(
                "Failed to send project approval email for project %s: %s", project.pk, exc
            )

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_ids(raw: str) -> list[int]:
        ids = []
        for part in (raw or '').split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    @staticmethod
    def _get_team_members(team_id: int, role_ids: list[int]):
        from apps.team_members.models import TeamMember
        qs = TeamMember.objects.filter(
            team_assignments__team_id=team_id,
            is_active=True,
        ).select_related('role')
        if role_ids:
            qs = qs.filter(role_id__in=role_ids)
        return list(qs)

    @staticmethod
    def _get_collab_members(project, role_ids: list[int]):
        from apps.team_members.models import TeamMember
        collab_team_ids = list(
            project.collaborators.values_list('pk', flat=True)
        )
        if not collab_team_ids:
            return []
        qs = TeamMember.objects.filter(
            team_assignments__team_id__in=collab_team_ids,
            is_active=True,
        ).select_related('role').distinct()
        if role_ids:
            qs = qs.filter(role_id__in=role_ids)
        return list(qs)

    @staticmethod
    def _get_contacts(contact_ids: list[int]):
        if not contact_ids:
            return []
        from apps.contacts.models import Contact
        return list(Contact.objects.filter(pk__in=contact_ids, is_active=True))

    @staticmethod
    def _collect_emails(*member_lists) -> set[str]:
        emails = set()
        for group in member_lists:
            for item in group:
                email = getattr(item, 'email_address', None) or getattr(item, 'email', None)
                if email:
                    emails.add(email)
        return emails

    @staticmethod
    def _get_run_cost_scenario(project, charge_type_ids: list[int], no_charge_type_ids: list[int]) -> str:
        if not project.run_cost_applies:
            return _RUN_COST_NO_COST
        type_id = project.project_type_id
        if type_id in charge_type_ids:
            return _RUN_COST_CHARGE
        if type_id in no_charge_type_ids:
            return _RUN_COST_NO_CHARGE
        return _RUN_COST_NO_CHARGE

    @staticmethod
    def _build_recharge_contacts_html(project, role_ids: list[int]) -> str:
        if not project.assigned_team_id:
            return ''
        from apps.team_members.models import TeamMember
        members = (
            TeamMember.objects
            .filter(
                team_assignments__team_id=project.assigned_team_id,
                role_id__in=role_ids,
                is_active=True,
            )
            .select_related('role')
        )
        items = [
            f'<li><strong>{escape(m.role.role)}:</strong> '
            f'{escape(m.display_name)} ({escape(m.email_address)})</li>'
            for m in members
        ]
        if not items:
            return ''
        return f'<ul>{"".join(items)}</ul>'

    @staticmethod
    def _build_member_mentions(members) -> str:
        return ' '.join(f'@{escape(m.display_name)}' for m in members if m.display_name)

    @staticmethod
    def _build_contact_mentions(contacts) -> str:
        return ' '.join(f'@{escape(c.name)}' for c in contacts if c.name)

    @classmethod
    def _build_variables(cls, *, project, estimate, team_members, collab_members,
                         info_contacts, finops_contacts, run_cost_scenario,
                         recharge_contacts_html, app_name) -> dict:
        from apps.projects.services import ProjectCodeService

        active_code = ProjectCodeService.get_active(project.pk)
        primary_label = project.labels.filter(is_primary=True).first()

        return {
            '{{ project_name }}': escape(project.name),
            '{{ programme_name }}': escape(project.programme.name) if project.programme else '',
            '{{ project_code }}': escape(active_code.code) if active_code else '',
            '{{ project_label }}': escape(primary_label.label) if primary_label else '',
            '{{ estimate_link }}': estimate.estimate_link or '',
            '{{ run_cost_applies }}': 'Yes' if project.run_cost_applies else 'No',
            '{{ run_cost_message }}': _RUN_COST_MESSAGES.get(run_cost_scenario, ''),
            '{{ recharge_contacts }}': recharge_contacts_html,
            '{{ assigned_team_mentions }}': cls._build_member_mentions(team_members),
            '{{ collaborator_mentions }}': cls._build_member_mentions(collab_members),
            '{{ info_contact_mentions }}': cls._build_contact_mentions(info_contacts),
            '{{ finops_contact_mentions }}': cls._build_contact_mentions(finops_contacts),
            '{{ app_name }}': escape(app_name),
        }

    @staticmethod
    def _substitute(text: str, variables: dict) -> str:
        for key, value in variables.items():
            text = text.replace(key, str(value))
        return text
