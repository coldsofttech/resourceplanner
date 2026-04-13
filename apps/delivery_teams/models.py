from django.db import models


class DeliveryTeam(models.Model):
    """
    Structure:
    * name: TEXT NOT NULL UNIQUE 120 CHARS
    * description: TEXT
    * member_count: INT DEFAULT 0 (maintained by post_save/post_delete signals on TeamMember)
    * is_active: BOOLEAN DEFAULT (TRUE)
    * created_at: DATETIME
    * updated_at: DATETIME
    """

    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(blank=True)
    member_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Cached count of active members. Maintained automatically via signals.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
