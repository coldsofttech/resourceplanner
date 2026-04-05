from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max


class SprintEngineService:
    """
    Generates Sprint rows for a Financial Year from configuration defaults.

    Algorithm
    ---------
    1. Sprint numbers are GLOBAL across all FYs — SP154–SP179 in FY1 means
       FY2 starts from SP180, not SP154 again.  The next number is derived
       from MAX(sprint_number) across the entire Sprint table.  Only when the
       table is completely empty does SPRINT_START_NUMBER take effect.

    2. Read SPRINT_DURATION_DAYS from Configurations (default 14 calendar days).

    3. The date cursor starts from the FY start_date, or from the day after the
       last existing sprint in this FY if the engine is being run incrementally.

    4. Sprints are generated until the FY end_date is reached or no room remains.
       The final sprint is clamped to fy.end_date so it never overflows.

    5. Sprints already in this FY that are marked is_overridden=True are skipped
       by sprint number — their dates are preserved unchanged.
    """

    @staticmethod
    def run(fy_id: int, dry_run: bool = False) -> dict:
        from apps.financial_years.models import FinancialYear
        from apps.configurations.services import ConfigurationService
        from apps.sprints.models import Sprint

        try:
            fy = FinancialYear.objects.get(pk=fy_id)
        except FinancialYear.DoesNotExist:
            raise ValidationError(f"Financial year {fy_id} does not exist.")

        duration_days = ConfigurationService.get_int('SPRINT_DURATION_DAYS', 14)
        if duration_days < 1:
            duration_days = 14

        name_prefix = ConfigurationService.get_str('SPRINT_NAME_PREFIX', 'Sprint')

        # Sprints already in this FY — used for cursor positioning and
        # overridden-number tracking only.  NOT used for number sequencing.
        fy_qs = Sprint.objects.filter(financial_year=fy)
        overridden_numbers = set(
            fy_qs.filter(is_overridden=True)
            .values_list('sprint_number', flat=True)
        )

        # ── Sprint number sequencing ───────────────────────────────────────
        # Numbers are global: query the entire table, not just this FY.
        # This prevents a new FY from restarting the sequence from
        # SPRINT_START_NUMBER when earlier FYs already have sprints.
        cfg_start = ConfigurationService.get_int('SPRINT_START_NUMBER', 1)
        global_max = Sprint.objects.aggregate(max_num=Max('sprint_number'))['max_num']
        if global_max is not None:
            # Table has at least one sprint — continue the global sequence.
            start_number = global_max + 1
        else:
            # Completely empty table — use the configured starting number.
            start_number = cfg_start

        fy_start: date = fy.start_date
        fy_end: date = fy.end_date

        # ── Date cursor ────────────────────────────────────────────────────
        # Resume from the day after the last sprint already in THIS FY,
        # or from the FY start if this FY has no sprints yet.
        last_fy_sprint = fy_qs.order_by('-end_date').first()
        cursor: date = (
            last_fy_sprint.end_date + timedelta(days=1)
            if last_fy_sprint
            else fy_start
        )

        created = []
        skipped = []
        sprint_number = start_number

        while cursor <= fy_end:
            sprint_end = cursor + timedelta(days=duration_days - 1)
            # Clamp the final sprint to the FY boundary.
            sprint_end = min(sprint_end, fy_end)

            if sprint_number in overridden_numbers:
                # Preserve the existing overridden sprint; advance both
                # the cursor and the number counter past it.
                skipped.append(sprint_number)
                cursor = sprint_end + timedelta(days=1)
                sprint_number += 1
                continue

            sprint_name = f"{name_prefix} {sprint_number}"

            if not dry_run:
                with transaction.atomic():
                    Sprint.objects.update_or_create(
                        financial_year=fy,
                        sprint_number=sprint_number,
                        defaults=dict(
                            sprint_name=sprint_name,
                            start_date=cursor,
                            end_date=sprint_end,
                            is_overridden=False,
                        ),
                    )

            created.append({
                'sprint_number': sprint_number,
                'sprint_name': sprint_name,
                'start_date': str(cursor),
                'end_date': str(sprint_end),
            })

            cursor = sprint_end + timedelta(days=1)
            sprint_number += 1

        return {
            'fy': fy.long_fy if hasattr(fy, 'long_fy') else str(fy),
            'generated': created,
            'skipped_overridden': skipped,
            'total_created': len(created),
            'dry_run': dry_run,
        }
