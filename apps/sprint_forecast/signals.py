from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='financial_years.FinancialYear')
def create_project_actuals_for_new_fy(sender, instance, created, **kwargs):
    """Auto-create ProjectActuals for all active projects when a new FY is created."""
    if not created:
        return
    from apps.projects.models import Project
    from .models import ProjectActuals
    for project in Project.objects.filter(is_active=True).iterator():
        ProjectActuals.objects.get_or_create(project=project)
