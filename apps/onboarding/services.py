import logging

from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from apps.business_units.models import BusinessUnit
from apps.contacts.models import Contact
from apps.project_types.models import ProjectType
from apps.projects.models import (
    Project, ProjectCode, ProjectComment, ProjectContact, ProjectLink,
)
from apps.projects.services import ProjectAttachmentService

from .models import (
    OnboardingRequest,
    OnboardingRequestAttachment,
    OnboardingRequestContact,
    OnboardingRequestLink,
)

logger = logging.getLogger(__name__)


def _name_from_email(email: str) -> str:
    local = email.split('@')[0]
    return local.replace('.', ' ').replace('_', ' ').replace('-', ' ').title()


def _get_default_project_type():
    try:
        from apps.configurations.services import ConfigurationService
        pt_id = ConfigurationService.get_str('ONBOARDING_DEFAULT_PROJECT_TYPE_ID', '')
        if pt_id:
            return ProjectType.objects.get(pk=int(pt_id))
    except Exception:
        pass
    return ProjectType.objects.filter(is_active=True).order_by('name').first()


def _get_or_create_contact(email: str) -> Contact:
    email = email.strip().lower()
    contact, _ = Contact.objects.get_or_create(
        email=email,
        defaults={'name': _name_from_email(email)},
    )
    return contact


@transaction.atomic
def process_onboarding_submission(
    project_name: str,
    requester_email: str,
    poc_emails: list[str],
    accountable_executive_email: str,
    business_unit_id,
    requirements: str,
    tentative_start_date,
    tentative_end_date,
    project_code: str,
    risk: str,
    links: list[dict],        # [{'url': ..., 'title': ...}]
    attachments: list[dict],  # [{'file_name': ..., 'content_type': ..., 'file_size': ..., 'file_data': ...}]
    submitted_from_ip=None,
) -> OnboardingRequest:
    project_type = _get_default_project_type()
    if not project_type:
        raise ValueError(
            "No project type is configured. Please add at least one project type or set ONBOARDING_DEFAULT_PROJECT_TYPE_ID."
        )

    bu = None
    if business_unit_id:
        try:
            bu = BusinessUnit.objects.get(pk=business_unit_id)
        except BusinessUnit.DoesNotExist:
            pass

    # Create the OnboardingRequest record
    req = OnboardingRequest.objects.create(
        project_name=project_name,
        requester_email=requester_email,
        accountable_executive_email=accountable_executive_email or '',
        business_unit=bu,
        requirements=requirements or '',
        tentative_start_date=tentative_start_date,
        tentative_end_date=tentative_end_date,
        project_code=project_code or '',
        risk=risk or '',
        submitted_from_ip=submitted_from_ip,
    )

    # Store contacts in onboarding record
    OnboardingRequestContact.objects.create(
        request=req,
        role=OnboardingRequestContact.ROLE_REQUESTER,
        email=requester_email,
        name=_name_from_email(requester_email),
    )
    for poc_email in poc_emails:
        poc_email = poc_email.strip()
        if poc_email:
            OnboardingRequestContact.objects.create(
                request=req,
                role=OnboardingRequestContact.ROLE_POC,
                email=poc_email,
                name=_name_from_email(poc_email),
            )

    # Store links in onboarding record
    for link in links:
        if link.get('url'):
            OnboardingRequestLink.objects.create(
                request=req,
                url=link['url'].strip(),
                title=link.get('title', '').strip() or _title_from_url(link['url']),
            )

    # Store attachments in onboarding record
    for att in attachments:
        OnboardingRequestAttachment.objects.create(
            request=req,
            file_name=att['file_name'],
            content_type=att.get('content_type', ''),
            file_size=att.get('file_size', 0),
            file_data=att.get('file_data'),
        )

    # --- Create the Project ---
    project_unique_name = project_name.strip()
    counter = 1
    base_name = project_unique_name
    while Project.objects.filter(name=project_unique_name).exists():
        counter += 1
        project_unique_name = f"{base_name} ({counter})"

    project = Project.objects.create(
        name=project_unique_name,
        project_type=project_type,
        status=Project.STATUS_NEW,
        tentative_start_date=tentative_start_date,
        tentative_end_date=tentative_end_date,
    )
    req.project = project
    req.save(update_fields=['project'])

    # Requester → Contact + ProjectContact (ROLE_PROJECT)
    requester_contact = _get_or_create_contact(requester_email)
    _add_project_contact(project, requester_contact)

    # POCs → Contact + ProjectContact (ROLE_PROJECT)
    for poc_email in poc_emails:
        poc_email = poc_email.strip()
        if poc_email and poc_email != requester_email:
            poc_contact = _get_or_create_contact(poc_email)
            _add_project_contact(project, poc_contact)

    # Requirements → ProjectComment
    if requirements and requirements.strip():
        ProjectComment.objects.create(
            project=project,
            comment=f"Requirements:\n{requirements.strip()}",
            posted_by=requester_email,
        )

    # Risk → ProjectComment
    if risk and risk.strip():
        ProjectComment.objects.create(
            project=project,
            comment=f"Risk if not delivered on time:\n{risk.strip()}",
            posted_by=requester_email,
        )

    # Project Code → ProjectCode
    if project_code and project_code.strip():
        ProjectCode.objects.create(
            project=project,
            code=project_code.strip(),
        )

    # Links → ProjectLink
    for link in links:
        if link.get('url'):
            ProjectLink.objects.create(
                project=project,
                url=link['url'].strip(),
                title=link.get('title', '').strip() or _title_from_url(link['url']),
            )

    # Attachments → ProjectAttachment
    for att in attachments:
        if att.get('file_name'):
            from apps.projects.models import ProjectAttachment
            ProjectAttachment.objects.create(
                project=project,
                file_name=att['file_name'],
                content_type=att.get('content_type', ''),
                file_size=att.get('file_size', 0),
                file_data=att.get('file_data'),
                uploaded_by=requester_email,
            )

    return req


def _add_project_contact(project, contact):
    try:
        ProjectContact.objects.get_or_create(
            project=project,
            contact=contact,
            role=ProjectContact.ROLE_PROJECT,
            defaults={'is_active': True},
        )
    except Exception as exc:
        logger.warning("Could not add contact %s to project %s: %s", contact.email, project.pk, exc)


def _title_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip('/').split('/') if p]
        label = parts[-1] if parts else parsed.netloc
        return label.replace('-', ' ').replace('_', ' ').title()[:200] or url[:200]
    except Exception:
        return url[:200]


def send_onboarding_confirmation_email(req: OnboardingRequest, request=None):
    try:
        from apps.email_templates.models import EmailTemplate, SCENARIO_ONBOARDING_SUBMITTED
        from apps.configurations.services import ConfigurationService

        app_name = ConfigurationService.get_str('APP_NAME', 'ResourcePlanner')
        from_email = ConfigurationService.get_str('EMAIL_HOST_USER', '') or None

        # Build project URL
        project_url = ''
        if req.project_id and request:
            project_url = request.build_absolute_uri(f'/projects/{req.project_id}/')
        elif req.project_id:
            project_url = f'/projects/{req.project_id}/'

        start_date = req.tentative_start_date.strftime('%d %b %Y') if req.tentative_start_date else '—'
        end_date = req.tentative_end_date.strftime('%d %b %Y') if req.tentative_end_date else '—'
        bu_name = req.business_unit.short_name if req.business_unit else '—'

        variables = {
            '{{ project_name }}': req.project_name,
            '{{ requester_email }}': req.requester_email,
            '{{ business_unit }}': bu_name,
            '{{ tentative_start_date }}': start_date,
            '{{ tentative_end_date }}': end_date,
            '{{ project_url }}': project_url,
            '{{ app_name }}': app_name,
        }

        try:
            tmpl = EmailTemplate.objects.select_related('header', 'footer').get(
                scenario=SCENARIO_ONBOARDING_SUBMITTED, is_active=True
            )
            subject = tmpl.subject or f"Your project demand has been submitted: {req.project_name}"
            body = tmpl.body or ''
            for key, val in variables.items():
                subject = subject.replace(key, str(val))
                body = body.replace(key, str(val))
            header_html = tmpl.header.content if tmpl.header else ''
            footer_html = tmpl.footer.content if tmpl.footer else ''
            full_body = f"{header_html}{body}{footer_html}"
        except EmailTemplate.DoesNotExist:
            logger.info("No onboarding_submitted email template configured — sending basic confirmation.")
            subject = f"Your project demand has been submitted: {req.project_name}"
            project_url_line = f'<p>View your project: <a href="{project_url}">{project_url}</a></p>' if project_url else ''
            full_body = (
                f"<p>Hi,</p>"
                f"<p>Your project demand <strong>{req.project_name}</strong> has been received.</p>"
                f"<ul>"
                f"<li>Business Unit: {bu_name}</li>"
                f"<li>Start: {start_date}</li>"
                f"<li>End: {end_date}</li>"
                f"</ul>"
                f"{project_url_line}"
                f"<p>Our team will review your request and get back to you.</p>"
                f"<p>— {app_name}</p>"
            )

        msg = EmailMessage(
            subject=subject,
            body=full_body,
            from_email=from_email,
            to=[req.requester_email],
        )
        msg.content_subtype = 'html'
        msg.send()
        logger.info("Onboarding confirmation email sent to %s", req.requester_email)

    except Exception as exc:
        logger.exception("Failed to send onboarding confirmation email: %s", exc)
