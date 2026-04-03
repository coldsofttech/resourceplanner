from django.db import models


class OfficeLocation(models.Model):
    """
    Structure:
    * city: TEXT NOT NULL 100 CHARS
    * country: TEXT NOT NULL 100 CHARS
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """
    city = models.CharField(
        max_length=100,
    )
    country = models.CharField(
        max_length=100,
    )
    is_active = models.BooleanField(
        default=True
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Only one location may be the default at a time. Used to pre-select in UI dropdowns.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['country', 'city']
        constraints = [
            models.UniqueConstraint(
                fields=["city", "country"],
                name="unique_office_city_country"
            )
        ]

    def __str__(self):
        return f"{self.city}, {self.country}"
