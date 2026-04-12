from django.db import models
from django.core.exceptions import ValidationError


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
    is_edited = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"Comment {self.pk} on project {self.project_id}"


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
