from django.db import models


class OnboardingRequest(models.Model):
    project_name = models.CharField(max_length=200)
    requester_email = models.EmailField()
    accountable_executive_email = models.EmailField(blank=True, default='')
    business_unit = models.ForeignKey(
        'business_units.BusinessUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_requests',
    )
    requirements = models.TextField(blank=True, default='')
    tentative_start_date = models.DateField(blank=True, null=True)
    tentative_end_date = models.DateField(blank=True, null=True)
    project_code = models.CharField(max_length=100, blank=True, default='')
    risk = models.TextField(blank=True, default='')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onboarding_requests',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_from_ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.project_name} ({self.requester_email})'


class OnboardingRequestContact(models.Model):
    ROLE_REQUESTER = 'REQUESTER'
    ROLE_POC = 'POC'
    ROLE_CHOICES = [
        (ROLE_REQUESTER, 'Requester'),
        (ROLE_POC, 'Point of Contact'),
    ]

    request = models.ForeignKey(
        OnboardingRequest,
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['role', 'email']

    def __str__(self):
        return f'{self.role}: {self.email}'


class OnboardingRequestLink(models.Model):
    request = models.ForeignKey(
        OnboardingRequest,
        on_delete=models.CASCADE,
        related_name='links',
    )
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.url


class OnboardingRequestAttachment(models.Model):
    request = models.ForeignKey(
        OnboardingRequest,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, default='')
    file_size = models.PositiveBigIntegerField(default=0)
    file_data = models.BinaryField(blank=True, null=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.file_name
