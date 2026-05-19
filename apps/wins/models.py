import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ── Weekly Win ────────────────────────────────────────────────────────────────

class Win(models.Model):
    STATUS_OPEN = 'open'
    STATUS_REVIEW_COMPLETE = 'review_complete'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_REVIEW_COMPLETE, 'Review Complete'),
    ]

    week_number = models.PositiveIntegerField(unique=True)
    week_start_date = models.DateField(help_text='Monday of the week.')
    week_end_date = models.DateField(help_text='Sunday of the week (auto-computed).')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wins_reviewed',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='wins_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_number']

    def __str__(self):
        return f'Week {self.week_number} ({self.week_start_date} – {self.week_end_date})'

    def clean(self):
        if self.week_start_date and self.week_start_date.weekday() != 0:
            raise ValidationError({'week_start_date': 'Week start date must be a Monday.'})

    def save(self, *args, **kwargs):
        if self.week_start_date and not self.week_end_date:
            import datetime
            self.week_end_date = self.week_start_date + datetime.timedelta(days=6)
        super().save(*args, **kwargs)


class WinEntry(models.Model):
    win = models.ForeignKey(Win, on_delete=models.CASCADE, related_name='entries')
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.CASCADE,
        related_name='win_entries',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='win_entries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['team__name', 'created_at']

    def __str__(self):
        return f'Win {self.win.week_number} / {self.team.name}: {self.title}'

    @property
    def display_label(self):
        """Short label for survey options: 'Week N: [i] Title'"""
        return self.title


# ── Monthly Wins ──────────────────────────────────────────────────────────────

class TeamProductOwner(models.Model):
    team = models.ForeignKey(
        'delivery_teams.DeliveryTeam',
        on_delete=models.CASCADE,
        related_name='product_owners',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_owner_teams',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('team', 'user')]
        ordering = ['team__name', 'user__email']

    def __str__(self):
        return f'{self.user.email} → {self.team.name}'


class MonthlyWin(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PHASE1_OPEN = 'phase1_open'
    STATUS_PHASE1_COMPLETE = 'phase1_complete'
    STATUS_PHASE2_OPEN = 'phase2_open'
    STATUS_DECLARED = 'declared'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PHASE1_OPEN, 'Phase 1 — Surveys Open'),
        (STATUS_PHASE1_COMPLETE, 'Phase 1 Complete'),
        (STATUS_PHASE2_OPEN, 'Phase 2 — Surveys Open'),
        (STATUS_DECLARED, 'Winners Declared'),
    ]

    name = models.CharField(max_length=200)
    wins = models.ManyToManyField(Win, related_name='monthly_wins', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    phase1_deadline = models.DateTimeField(null=True, blank=True)
    phase2_deadline = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='monthly_wins_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


CATEGORY_DELIVERY = 'delivery'
CATEGORY_OPERATIONAL = 'operational_excellence'
CATEGORY_CHOICES = [
    (CATEGORY_DELIVERY, 'Delivery'),
    (CATEGORY_OPERATIONAL, 'Operational Excellence'),
]


class MonthlyWinSurvey(models.Model):
    PHASE_1 = 'phase1'
    PHASE_2 = 'phase2'
    PHASE_CHOICES = [
        (PHASE_1, 'Phase 1'),
        (PHASE_2, 'Phase 2'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_OVERRIDDEN = 'overridden'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_OVERRIDDEN, 'Overridden'),
    ]

    monthly_win = models.ForeignKey(MonthlyWin, on_delete=models.CASCADE, related_name='surveys')
    phase = models.CharField(max_length=10, choices=PHASE_CHOICES)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='monthly_win_surveys',
    )
    # Phase 1 only: which teams this PO is responsible for in this monthly win
    teams = models.ManyToManyField('delivery_teams.DeliveryTeam', blank=True, related_name='monthly_win_surveys')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['recipient__email']

    def __str__(self):
        return f'{self.monthly_win.name} / {self.phase} / {self.recipient.email}'


class MonthlyWinSurveyNomination(models.Model):
    survey = models.ForeignKey(MonthlyWinSurvey, on_delete=models.CASCADE, related_name='nominations')
    entry = models.ForeignKey(WinEntry, on_delete=models.CASCADE, related_name='nominations')
    category = models.CharField(max_length=25, choices=CATEGORY_CHOICES)
    is_dismissed = models.BooleanField(default=False)
    dismissed_reason = models.CharField(max_length=300, blank=True)
    nominated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('survey', 'entry', 'category')]
        ordering = ['category', 'entry__team__name']

    def __str__(self):
        return f'{self.survey} / {self.category} / {self.entry_id}'


class MonthlyWinResult(models.Model):
    monthly_win = models.ForeignKey(MonthlyWin, on_delete=models.CASCADE, related_name='results')
    entry = models.ForeignKey(WinEntry, on_delete=models.CASCADE, related_name='monthly_results')
    category = models.CharField(max_length=25, choices=CATEGORY_CHOICES)
    rank = models.PositiveIntegerField()
    vote_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('monthly_win', 'category', 'rank')]
        ordering = ['category', 'rank']

    def __str__(self):
        return f'{self.monthly_win.name} / {self.category} / #{self.rank}'
