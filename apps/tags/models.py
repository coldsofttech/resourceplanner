from django.db import models
from django.db.models.functions import Lower


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="unique_tag_name_case_insensitive"
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        if not self.name.startswith("#"):
            self.name = f"#{self.name}"
        super().save(*args, **kwargs)
