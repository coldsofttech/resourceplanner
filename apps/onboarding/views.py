import logging

from django.shortcuts import render
from django.views.generic import View

from apps.business_units.models import BusinessUnit

from .services import process_onboarding_submission, send_onboarding_confirmation_email

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class OnboardingFormView(View):
    template_name = 'onboarding/form.html'

    def _base_template(self, request):
        if request.user.is_authenticated:
            return 'base.html'
        return 'onboarding/standalone.html'

    def _context(self, request, errors=None, data=None):
        business_units = list(
            BusinessUnit.objects.filter(is_active=True).values('id', 'full_name', 'short_name').order_by('full_name')
        )
        ctx = {
            'business_units': business_units,
            'errors': errors or {},
            'data': data or {},
            'base_template': self._base_template(request),
        }
        # Pre-fill requester email for authenticated users (allow override from data on POST errors)
        if request.user.is_authenticated and not (data and data.get('requester_email')):
            ctx['data'] = dict(ctx['data'], requester_email=request.user.email)
        return ctx

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        data = request.POST
        files = request.FILES

        errors = {}
        project_name = data.get('project_name', '').strip()
        # For authenticated users, always use their account email regardless of form value
        if request.user.is_authenticated:
            requester_email = request.user.email
        else:
            requester_email = data.get('requester_email', '').strip()
        poc_emails_raw = data.getlist('poc_emails')
        accountable_executive_email = data.get('accountable_executive_email', '').strip()
        business_unit_id = data.get('business_unit_id') or None
        requirements = data.get('requirements', '').strip()
        tentative_start_date = data.get('tentative_start_date') or None
        tentative_end_date = data.get('tentative_end_date') or None
        project_code = data.get('project_code', '').strip()
        risk = data.get('risk', '').strip()
        link_urls = data.getlist('link_url')

        if not project_name:
            errors['project_name'] = 'Project name is required.'
        if not requester_email:
            errors['requester_email'] = 'Requester email is required.'
        if not requirements:
            errors['requirements'] = 'Requirements are required.'

        poc_emails = [e.strip() for e in poc_emails_raw if e.strip()]

        if errors:
            return render(request, self.template_name, self._context(request, errors=errors, data=data))

        # Parse dates
        from datetime import datetime
        parsed_start = None
        parsed_end = None
        if tentative_start_date:
            try:
                parsed_start = datetime.strptime(tentative_start_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        if tentative_end_date:
            try:
                parsed_end = datetime.strptime(tentative_end_date, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Collect links
        link_titles = data.getlist('link_title')
        links = []
        for i, url in enumerate(link_urls):
            url = url.strip()
            if url:
                title = link_titles[i].strip() if i < len(link_titles) else ''
                links.append({'url': url, 'title': title})

        # Collect attachments
        attachments = []
        for f in files.getlist('attachments'):
            attachments.append({
                'file_name': f.name,
                'content_type': f.content_type or '',
                'file_size': f.size,
                'file_data': f.read(),
            })

        try:
            req = process_onboarding_submission(
                project_name=project_name,
                requester_email=requester_email,
                poc_emails=poc_emails,
                accountable_executive_email=accountable_executive_email,
                business_unit_id=business_unit_id,
                requirements=requirements,
                tentative_start_date=parsed_start,
                tentative_end_date=parsed_end,
                project_code=project_code,
                risk=risk,
                links=links,
                attachments=attachments,
                submitted_from_ip=_get_client_ip(request),
            )
            send_onboarding_confirmation_email(req, request=request)
            return render(request, 'onboarding/success.html', {
                'project_name': project_name,
                'requester_email': requester_email,
            })
        except ValueError as exc:
            errors['non_field_errors'] = str(exc)
            return render(request, self.template_name, self._context(request, errors=errors, data=data))
        except Exception as exc:
            logger.exception("Error processing onboarding submission: %s", exc)
            errors['non_field_errors'] = 'An unexpected error occurred. Please try again or contact support.'
            return render(request, self.template_name, self._context(request, errors=errors, data=data))
