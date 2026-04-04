from django.core.exceptions import ValidationError
from django.db import models


class FinancialYear(models.Model):
    """
    Represents a financial year used across the planner.

    Structure:
    * start_date:    DATE NOT NULL              — first day of the FY (e.g. 2024-04-01)
    * end_date:      DATE NOT NULL              — last day of the FY  (e.g. 2025-03-31)
    * long_fy:       CHAR(9)  auto-generated   — e.g. "FY2024-2025"
    * short_fy:      CHAR(7)  auto-generated   — e.g. "FY24-25"
    * span_days:     INT      auto-calculated  — total calendar days in the FY
    * is_active:     BOOLEAN  DEFAULT FALSE    — only one FY may be active at a time
    * notes:         TEXT     optional
    * created_at:    DATETIME auto
    * updated_at:    DATETIME auto
    """
    start_date = models.DateField()
    end_date = models.DateField()
    long_fy = models.CharField(
        max_length=11,
        editable=False,
        help_text='e.g. FY2024-2025',
    )
    short_fy = models.CharField(
        max_length=7,
        editable=False,
        help_text='e.g. FY24-25',
    )
    span_days = models.PositiveIntegerField(
        editable=False,
        default=0,
        help_text='Total calendar days from start_date to end_date (inclusive).',
    )
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Only one financial year may be active at a time.',
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.long_fy

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError(
                    {'end_date': 'End date must be after start date.'}
                )

            overlapping = FinancialYear.objects.filter(
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(pk=self.pk)

            if overlapping.exists():
                raise ValidationError(
                    'This financial year overlaps with an existing one.'
                )

    @staticmethod
    def _build_long_fy(start_date, end_date):
        """FY2024-2025 — uses the calendar year of start_date and end year."""
        return f'FY{start_date.year}-{str(end_date.year)}'

    @staticmethod
    def _build_short_fy(start_date, end_date):
        """FY24-25 — two-digit year of start and two-digit year of end."""
        return f'FY{str(start_date.year)[2:]}-{str(end_date.year)[2:]}'

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.long_fy = self._build_long_fy(self.start_date, self.end_date)
            self.short_fy = self._build_short_fy(self.start_date, self.end_date)
            self.span_days = (self.end_date - self.start_date).days + 1

        super().save(*args, **kwargs)
