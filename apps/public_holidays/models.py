from django.db import models


class PublicHoliday(models.Model):
    """
    A public holiday for a specific office location on a given date.

    Structure:
    * location: FK OfficeLocation NOT NULL
    * date: DATE NOT NULL
    * name: TEXT NOT NULL 120 CHARS — the holiday name, e.g. "Christmas Day"
    * created_at: DATETIME
    * updated_at: DATETIME

    Unique together: (location, date) — a location can only have one holiday per day.
    """

    location = models.ForeignKey(
        'office_locations.OfficeLocation',
        on_delete=models.PROTECT,
        related_name='public_holidays',
        help_text='The office location this holiday applies to.',
    )
    date = models.DateField(
        help_text='The calendar date of the public holiday.',
    )
    name = models.CharField(
        max_length=120,
        help_text='Name of the public holiday, e.g. "Christmas Day".',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'location']
        unique_together = [('location', 'date')]

    def __str__(self):
        return f"{self.name} — {self.location} ({self.date})"
