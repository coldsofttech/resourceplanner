from django.db import models


class MemberLeave(models.Model):
    """
    A confirmed leave record for a team member.

    Half-day leaves are modelled via start_date == end_date combined with
    is_half_day=True and half_day_period ('AM' or 'PM'). The service calculates
    days accordingly (0.5 instead of 1.0 for a single-day half-day).

    Structure:
    * member          FK TeamMember NOT NULL
    * start_date      DATE NOT NULL
    * end_date        DATE NOT NULL  (>= start_date always)
    * is_half_day     BOOL DEFAULT False  — only meaningful when start_date == end_date
    * half_day_period CHAR(2) NULL  — 'AM' or 'PM', only set when is_half_day=True
    * days            DECIMAL(6,2)  — auto-calculated, never written by callers directly
    * note            TEXT optional
    * created_at      DATETIME
    * updated_at      DATETIME
    """

    HALF_DAY_AM = 'AM'
    HALF_DAY_PM = 'PM'
    HALF_DAY_CHOICES = [
        (HALF_DAY_AM, 'Morning (AM)'),
        (HALF_DAY_PM, 'Afternoon (PM)'),
    ]

    member = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.CASCADE,
        related_name='leaves',
        help_text='The team member this leave record belongs to.',
    )
    start_date = models.DateField(
        help_text='First day of leave (inclusive).',
    )
    end_date = models.DateField(
        help_text='Last day of leave (inclusive). Must be >= start_date.',
    )
    is_half_day = models.BooleanField(
        default=False,
        help_text='True when the leave covers only half a working day. '
                  'Only valid when start_date == end_date.',
    )
    half_day_period = models.CharField(
        max_length=2,
        choices=HALF_DAY_CHOICES,
        null=True,
        blank=True,
        help_text='Which half of the day is taken. Required when is_half_day=True.',
    )
    days = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        editable=False,
        help_text='Working days consumed (auto-calculated, excludes weekends and '
                  'public holidays for the member\'s location).',
    )
    note = models.TextField(
        blank=True,
        null=True,
        default='',
        help_text='Optional free-text note about the leave.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date', 'member']

    def __str__(self):
        half = ' (half day)' if self.is_half_day else ''
        return f"{self.member} — {self.start_date} to {self.end_date}{half}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date must be on or after start_date.")
        if self.is_half_day:
            if self.start_date and self.end_date and self.start_date != self.end_date:
                raise ValidationError("Half-day leave must have start_date equal to end_date.")
            if not self.half_day_period:
                raise ValidationError("half_day_period is required for half-day leaves.")
        else:
            self.half_day_period = None


class LeaveDay(models.Model):
    """
    One row per calendar date per team member that is consumed by a leave record.
    Allows O(1) availability lookups during resource planning.

    is_half_day=True rows represent 0.5 days consumed.
    Half-day period is preserved for display/conflict purposes.

    These rows are always derived — they are regenerated from MemberLeave whenever
    a leave record or a public holiday is created/updated/deleted.
    """

    HALF_DAY_AM = 'AM'
    HALF_DAY_PM = 'PM'
    HALF_DAY_CHOICES = [
        (HALF_DAY_AM, 'Morning (AM)'),
        (HALF_DAY_PM, 'Afternoon (PM)'),
    ]

    member = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.CASCADE,
        related_name='leave_days',
        help_text='The team member whose availability is affected.',
    )
    leave = models.ForeignKey(
        MemberLeave,
        on_delete=models.CASCADE,
        related_name='leave_days',
        help_text='The parent leave record that produced this day.',
    )
    date = models.DateField(
        help_text='The specific calendar date that is a leave day.',
    )
    is_half_day = models.BooleanField(
        default=False,
        help_text='True when only half a day is consumed on this date.',
    )
    half_day_period = models.CharField(
        max_length=2,
        choices=HALF_DAY_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['date', 'member']
        unique_together = [('member', 'date', 'leave')]

    def __str__(self):
        half = f' ({self.half_day_period})' if self.is_half_day else ''
        return f"{self.member} — {self.date}{half}"
