"""
Signals that auto-expire resource plans when their scoped entity moves to
a completed/closed state.

Wired into: FinancialYear, Project, Programme models via post_save signal.

Status rules:
  - FinancialYear: expires plans when is_active becomes False (year closed)
  - Project:       expires plans when status is COMPLETED or CANCELLED
  - Programme:     expires plans when is_active becomes False
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


def _connect_financial_year():
    try:
        from apps.financial_years.models import FinancialYear
        from .services import ResourcePlanService

        @receiver(
            post_save, sender=FinancialYear, dispatch_uid="rp_expire_on_fy_inactive"
        )
        def expire_plans_on_fy_inactive(sender, instance, **kwargs):
            # Skip on initial creation
            if kwargs.get("created"):
                return
            # Only act when is_active was explicitly updated
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "is_active" not in update_fields:
                return
            if not instance.is_active:
                ResourcePlanService.expire_plans_for_fy(instance)

    except ImportError:
        pass


def _connect_project():
    try:
        from apps.projects.models import Project
        from .services import ResourcePlanService

        TERMINAL_STATUSES = {"COMPLETED", "CANCELLED"}

        @receiver(
            post_save, sender=Project, dispatch_uid="rp_expire_on_project_complete"
        )
        def expire_plans_on_project_complete(sender, instance, **kwargs):
            if kwargs.get("created"):
                return
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "status" not in update_fields:
                return
            if getattr(instance, "status", None) in TERMINAL_STATUSES:
                ResourcePlanService.expire_plans_for_project(instance)

    except ImportError:
        pass


def _connect_programme():
    try:
        from apps.programmes.models import Programme  # corrected import
        from .services import ResourcePlanService

        @receiver(
            post_save, sender=Programme, dispatch_uid="rp_expire_on_programme_inactive"
        )
        def expire_plans_on_programme_inactive(sender, instance, **kwargs):
            if kwargs.get("created"):
                return
            update_fields = kwargs.get("update_fields")
            if update_fields is not None and "is_active" not in update_fields:
                return
            if not instance.is_active:
                ResourcePlanService.expire_plans_for_programme(instance)

    except ImportError:
        pass


# Wire all signals
_connect_financial_year()
_connect_project()
_connect_programme()
