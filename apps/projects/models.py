from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from apps.contacts.models import Contact

from .utils import get_tshirt_size


class Project(models.Model):
    STATUS_NEW = "NEW"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_ON_HOLD = "ON_HOLD"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_ON_HOLD, "On Hold"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    CONFIDENCE_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("VERY_HIGH", "Very High"),
    ]

    name = models.CharField(max_length=200, unique=True)
    project_type = models.ForeignKey(
        "project_types.ProjectType",
        on_delete=models.PROTECT,
        related_name="projects",
    )
    programme = models.ForeignKey(
        "programmes.Programme",
        on_delete=models.PROTECT,
        related_name="projects",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    sub_status = models.ForeignKey(
        "project_sub_statuses.ProjectSubStatus",
        on_delete=models.SET_NULL,
        related_name="projects",
        blank=True,
        null=True,
    )
    assigned_team = models.ForeignKey(
        "delivery_teams.DeliveryTeam",
        on_delete=models.SET_NULL,
        related_name="assigned_projects",
        blank=True,
        null=True,
    )
    collaborators = models.ManyToManyField(
        "delivery_teams.DeliveryTeam",
        through="ProjectCollaborator",
        related_name="collaborating_projects",
        blank=True,
    )
    efforts_issued = models.BooleanField(default=False)
    effort_issue_commitment_date = models.DateField(blank=True, null=True)
    run_cost_applies = models.BooleanField(default=False)
    confidence = models.CharField(
        max_length=20,
        choices=CONFIDENCE_CHOICES,
        blank=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        blank=True,
    )
    tentative_start_date = models.DateField(blank=True, null=True)
    tentative_end_date = models.DateField(blank=True, null=True)
    completed_sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='completed_projects',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        programme_name = self.programme.name if self.programme else "Others"
        return f"{programme_name}: {self.name}"

    def clean(self):
        errors = {}
        if self.status == self.STATUS_IN_PROGRESS:
            if not (self.code or "").strip():
                errors["code"] = "Code is required when status is In Progress."
            if not self.assigned_team_id:
                errors["assigned_team"] = (
                    "Assigned team is required when status is In Progress."
                )
        if errors:
            raise ValidationError(errors)


class ProjectCollaborator(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_collaborators",
    )
    team = models.ForeignKey(
        "delivery_teams.DeliveryTeam",
        on_delete=models.CASCADE,
        related_name="team_collaborations",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "team")]
        ordering = ["team__name"]

    def __str__(self):
        return f"{self.project.name} \u2194 {self.team.name}"

    def clean(self):
        if self.project_id and self.team_id:
            if self.team_id == self.project.assigned_team_id:
                raise ValidationError(
                    {
                        "team": "A collaborating team cannot be the same as the assigned team."
                    }
                )


class ProjectLabel(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="labels",
        null=True,
    )
    label = models.CharField(max_length=50, unique=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "label"]

    def __str__(self):
        return self.label


class ProjectStatusHistory(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    previous_sub_status = models.ForeignKey(
        "project_sub_statuses.ProjectSubStatus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    new_sub_status = models.ForeignKey(
        "project_sub_statuses.ProjectSubStatus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project_id}: {self.previous_status} → {self.new_status}"


class ProjectTag(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="project_tags"
    )
    tag = models.ForeignKey(
        "tags.Tag", on_delete=models.PROTECT, related_name="project_tags"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "tag")
        ordering = ["tag__name"]

    def __str__(self):
        return f"{self.project_id} — #{self.tag.name}"


class ProjectComment(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="comments"
    )
    comment = models.TextField()
    posted_by = models.CharField(max_length=200, default="Anonymous")
    posted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='project_comments',
    )
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='project_comment_mentions',
    )
    is_edited = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"Comment {self.pk} on project {self.project_id}"


class ProjectCommentAttachment(models.Model):
    """File attachments on project comments (images or documents)."""
    comment = models.ForeignKey(
        ProjectComment, on_delete=models.CASCADE, related_name='attachments'
    )
    file_name    = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, default='')
    file_size    = models.PositiveBigIntegerField(default=0)
    file_data    = models.BinaryField(blank=True, null=True)
    file_path    = models.CharField(max_length=1000, blank=True, default='')
    s3_key       = models.CharField(max_length=1000, blank=True, default='')
    uploaded_by  = models.CharField(max_length=200, default='')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.file_name} (comment {self.comment_id})'


class ProjectFollower(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='followers'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followed_projects',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('project', 'user')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_id} follows {self.project_id}'


class ProjectCode(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="codes",
    )
    code = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} ({self.created_at:%Y-%m-%d})"


class ProjectEstimate(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_REVIEWED = "REVIEWED"
    STATUS_SHARED = "SHARED"
    STATUS_APPROVED = "APPROVED"
    STATUS_SUPERSEDED = "SUPERSEDED"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_SHARED, "Shared"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_SUPERSEDED, "Superseded"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="estimates",
    )
    version = models.PositiveIntegerField(editable=False)
    estimate_link = models.URLField(blank=True, null=True)
    shared_by = models.CharField(max_length=200, blank=True)
    reviewed_by = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    estimate_days = models.DecimalField(max_digits=8, decimal_places=2)
    contingency_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    day_rate = models.DecimalField(max_digits=10, decimal_places=2)
    approval_email_sent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version"]
        unique_together = [("project", "version")]

    def __str__(self):
        return f"{self.project} — {self.version_label}"

    @property
    def version_label(self):
        return f"v{self.version}"

    @property
    def total_cost(self):
        return (
            self.estimate_days
            * self.day_rate
            * (1 + self.contingency_pct / Decimal("100"))
        )

    @property
    def tshirt_size(self):
        return get_tshirt_size(self.total_cost)


class ProjectEstimateHistory(models.Model):
    ACTION_CREATED = "CREATED"
    ACTION_UPDATED = "UPDATED"
    ACTION_APPROVED = "APPROVED"
    ACTION_SUPERSEDED = "SUPERSEDED"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_APPROVED, "Approved"),
        (ACTION_SUPERSEDED, "Superseded"),
    ]

    estimate = models.ForeignKey(
        ProjectEstimate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="estimate_history",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.estimate} — {self.action}"


class ProjectBudget(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    financial_year = models.ForeignKey(
        "financial_years.FinancialYear",
        on_delete=models.PROTECT,
        related_name="project_budgets",
    )
    allocated_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    refined_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    estimate_version = models.ForeignKey(
        ProjectEstimate,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="budget_links",
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("project", "financial_year")
        ordering = ["financial_year__start_date"]

    def __str__(self):
        return f"{self.project} — {self.financial_year}"

    @property
    def actual_budget(self):
        val = (
            self.refined_budget
            if self.refined_budget is not None
            else self.allocated_budget
        )
        if val is None:
            return None
        return Decimal(str(val))

    @property
    def remaining_budget(self):
        actual = self.actual_budget
        if actual is None:
            return None
        if self.estimate_version is None:
            return actual
        return actual - Decimal(str(self.estimate_version.total_cost))


class ProjectBudgetHistory(models.Model):
    ACTION_CREATED = "CREATED"
    ACTION_UPDATED = "UPDATED"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
    ]

    budget = models.ForeignKey(
        ProjectBudget,
        on_delete=models.SET_NULL,
        null=True,
        related_name="history",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="budget_history",
    )
    financial_year = models.ForeignKey(
        "financial_years.FinancialYear",
        on_delete=models.PROTECT,
        related_name="budget_history",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    previous_allocated_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    previous_refined_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    previous_estimate_version = models.ForeignKey(
        ProjectEstimate,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="budget_history_previous",
    )
    previous_total_cost = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )

    new_allocated_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    new_refined_budget = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )
    new_estimate_version = models.ForeignKey(
        ProjectEstimate,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="budget_history_new",
    )
    new_total_cost = models.DecimalField(
        max_digits=14, decimal_places=2, blank=True, null=True
    )

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} — {self.project} / {self.financial_year} @ {self.created_at}"


class ProjectContact(models.Model):
    ROLE_PROJECT = "PROJECT"
    ROLE_FINANCE = "FINANCE"
    ROLE_CHOICES = [
        (ROLE_PROJECT, "Project"),
        (ROLE_FINANCE, "Finance"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_contacts",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="project_contact_assignments",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project", "contact", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "contact", "role"],
                name="unique_project_contact_role",
            )
        ]

    def __str__(self):
        return f"{self.project.name} — {self.role} | {self.contact.email}"


class ProjectContactHistory(models.Model):
    ROLE_PROJECT = "PROJECT"
    ROLE_FINANCE = "FINANCE"
    ROLE_CHOICES = [
        (ROLE_PROJECT, "Project"),
        (ROLE_FINANCE, "Finance"),
    ]

    ACTION_ADDED = "ADDED"
    ACTION_REMOVED = "REMOVED"
    ACTION_CHOICES = [
        (ACTION_ADDED, "Added"),
        (ACTION_REMOVED, "Removed"),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_contact_history",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="contacts_history",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True, default="")  # optional on remove
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.contact} — {self.action} ({self.role})"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("History records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("History records cannot be deleted.")


class ProjectLink(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="links",
    )
    title = models.CharField(max_length=200)
    url = models.URLField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.project})"


class ProjectAttachment(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True, default="")
    file_size = models.PositiveBigIntegerField(default=0)
    # Populated based on PROJECT_ATTACHMENT_STORAGE setting
    file_data = models.BinaryField(blank=True, null=True)   # database backend
    file_path = models.CharField(max_length=1000, blank=True, default="")  # local backend
    s3_key = models.CharField(max_length=1000, blank=True, default="")     # s3 backend
    uploaded_by = models.CharField(max_length=200, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.project})"


class ProjectView(models.Model):
    name = models.CharField(max_length=100, unique=True)
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    ordering = models.CharField(max_length=50, blank=True, default="-created_at")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
