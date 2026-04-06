from django.db import models


class ProjectSubStatus(models.Model):
    MAIN_STATUS_CHOICES = [
        ('NEW', 'New'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    name = models.CharField(max_length=100)
    main_status = models.CharField(max_length=20, choices=MAIN_STATUS_CHOICES)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['main_status', 'order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'main_status'],
                name='unique_name_per_main_status'
            ),
            models.UniqueConstraint(
                fields=['main_status', 'order'],
                name='unique_order_per_main_status'
            ),
        ]

    def __str__(self):
        return f'{self.main_status()}: {self.name}'
