import re

from django.conf import settings
from django.db import models


class Todo(models.Model):
    STATUS_OPEN        = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE        = 'done'
    STATUS_CHOICES = [
        (STATUS_OPEN,        'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE,        'Done'),
    ]

    PRIORITY_LOW    = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH   = 'high'
    PRIORITY_URGENT = 'urgent'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW,    'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH,   'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]

    RECURRENCE_DAILY   = 'daily'
    RECURRENCE_WEEKLY  = 'weekly'
    RECURRENCE_MONTHLY = 'monthly'
    RECURRENCE_YEARLY  = 'yearly'
    RECURRENCE_CHOICES = [
        (RECURRENCE_DAILY,   'Daily'),
        (RECURRENCE_WEEKLY,  'Weekly'),
        (RECURRENCE_MONTHLY, 'Monthly'),
        (RECURRENCE_YEARLY,  'Yearly'),
    ]

    title       = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    due_date    = models.DateField(null=True, blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='todos_assigned',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='todos_created',
    )

    is_recurring       = models.BooleanField(default=False)
    recurrence_rule    = models.CharField(
        max_length=10, choices=RECURRENCE_CHOICES, blank=True,
    )
    recurrence_interval = models.PositiveIntegerField(default=1)
    recurrence_end_date = models.DateField(null=True, blank=True)
    parent_todo = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='recurrence_children',
    )

    completed_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', 'due_date', '-priority', '-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if self.status == self.STATUS_DONE or not self.due_date:
            return False
        from datetime import date
        return self.due_date < date.today()


class TodoComment(models.Model):
    todo       = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name='comments')
    content    = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='todo_comments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment on Todo#{self.todo_id} by {self.created_by_id}'

    @staticmethod
    def extract_mention_handles(text):
        """Return list of @handle strings found in text (e.g. ['alice', 'bob.smith'])."""
        return re.findall(r'@([\w.+-]+)', text)
