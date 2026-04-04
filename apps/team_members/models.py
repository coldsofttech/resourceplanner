from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models

_EMAIL_VALIDATOR = EmailValidator(
    message="Please enter a valid email address.",
)


def get_default_holidays():
    from apps.configurations.services import ConfigurationService
    return ConfigurationService.get_int("DEFAULT_HOLIDAYS", 20)


class TeamMember(models.Model):
    """
    Structure:
    * first_name: TEXT NOT NULL 80 CHARS
    * last_name: TEXT NOT NULL 80 CHARS
    * display_name: TEXT NOT NULL 165 CHARS
    * email_address: TEXT NOT NULL UNIQUE 254 CHARS
    * skills: FK Skill (Many to Many)
    * location: FK OfficeLocation NOT NULL
    * employment_type: FK OfficeEmploymentType NOT NULL
    * role: FK TeamRole NOT NULL
    * team: FK DeliveryTeam
    * start_date: DATETIME NOT NULL
    * end_date: DATETIME
    * default_holidays: INT NOT NULL
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    first_name = models.CharField(
        max_length=80,
    )
    last_name = models.CharField(
        max_length=80,
    )
    display_name = models.CharField(
        max_length=165,
        help_text='Auto-generated as "Last Name, First Name". Override if needed.'
    )
    email_address = models.CharField(
        max_length=254,
        validators=[_EMAIL_VALIDATOR],
    )
    skills = models.ManyToManyField(
        'skills.Skill',
        blank=True,
        related_name='member_skills',
    )
    location = models.ForeignKey(
        'office_locations.OfficeLocation',
        on_delete=models.PROTECT,
        related_name='member_location',
    )
    employment_type = models.ForeignKey(
        'employment_types.EmploymentType',
        on_delete=models.PROTECT,
        related_name='member_employment_type',
    )
    role = models.ForeignKey(
        'team_roles.TeamRole',
        on_delete=models.PROTECT,
        related_name='member_role',
    )
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='member_team',
    )
    start_date = models.DateField(
        help_text='Date the member joined / became available for planning.'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date the member leaves. Null means currently active.'
    )
    default_holidays = models.PositiveIntegerField(
        default=get_default_holidays,
        help_text="Holiday days per financial year. Defaults to the system DEFAULT_HOLIDAYS.",
    )
    is_active = models.BooleanField(
        default=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = f"{self.last_name.strip()}, {self.first_name.strip()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({
                "end_date": "End date cannot be before start date.",
            })

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class TeamMemberHistory(models.Model):
    """
    Structure:
    * member: FK TeamMember NOT NULL
    * from_team: FK DeliveryTeam
    * to_team: FK DeliveryTeam
    * moved_on: DATETIME
    * note: TEXT
    * created_at: DATETIME
    """
    member = models.ForeignKey(
        TeamMember,
        on_delete=models.CASCADE,
        related_name='team_history',
    )
    from_team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    to_team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    moved_on = models.DateField(
        help_text='Effective date of the team change.',
    )
    note = models.TextField(
        blank=True,
        help_text='Optional: Reason for the move.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-moved_on', '-created_at']

    def __str__(self):
        return (
            f"{self.member} - "
            f"{self.from_team or 'No team'} → {self.to_team or 'No team'} "
            f"on {self.moved_on}"
        )
