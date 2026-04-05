from django.db import models


class SprintCapacity(models.Model):
    """
    Materialised per-member capacity for a sprint.

    Regenerated automatically (via signals) whenever any of the following
    change: Sprint, TeamMember, PublicHoliday, or MemberLeave.

    Fields
    ------
    sprint          : FK → Sprint (cascade delete).
    team_member     : FK → TeamMember (cascade delete).
    working_days    : Calendar working days in the sprint window
                      (Mon–Fri, excluding weekends).
    holiday_days    : Public holidays for the member's location that fall
                      within the sprint window (Mon–Fri only).
    leave_days      : Confirmed leave days for the member that overlap the
                      sprint (only working days are counted).
    net_capacity    : working_days − holiday_days − leave_days.
                      Stored denormalised for fast grid queries.
    """

    sprint = models.ForeignKey(
        'sprints.Sprint',
        on_delete=models.CASCADE,
        related_name='capacities',
    )
    team_member = models.ForeignKey(
        'team_members.TeamMember',
        on_delete=models.CASCADE,
        related_name='sprint_capacities',
    )
    working_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    holiday_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    leave_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    net_capacity = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sprint', 'team_member', 'net_capacity']
        unique_together = [('sprint', 'team_member')]

    def __str__(self):
        return f"{self.team_member} — {self.sprint} (net: {self.net_capacity}d)"
