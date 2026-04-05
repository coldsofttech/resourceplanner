import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from .models import SprintCapacity

logger = logging.getLogger(__name__)


def _working_days_in_range(start: date, end: date) -> int:
    """Count Mon–Fri days between start and end (inclusive)."""
    if start > end:
        return 0
    total = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            total += 1
        current += timedelta(days=1)
    return total


class SprintCapacityService:
    """
    Computes and persists SprintCapacity rows.
    All public methods are idempotent — safe to call multiple times.
    """

    @staticmethod
    def _compute(sprint, member) -> dict:
        """
        Return a dict with working_days / holiday_days / leave_days / net_capacity
        for a single sprint × member combination.
        """
        s_start = sprint.start_date
        s_end = sprint.end_date
        location = getattr(member, 'location', None)

        member_start = getattr(member, 'start_date', None)
        member_end = getattr(member, 'end_date', None)

        if member_start:
            s_start = max(s_start, member_start)
        if member_end:
            s_end = min(s_end, member_end)

        # Member was not active at all during this sprint.
        if s_start > s_end:
            return {
                'working_days': Decimal('0'),
                'holiday_days': Decimal('0'),
                'leave_days': Decimal('0'),
                'net_capacity': Decimal('0'),
            }

        # 1. Working days (Mon–Fri) in the sprint window
        working = _working_days_in_range(s_start, s_end)

        # 2. Public holidays for the member's location that fall in this sprint
        holidays = Decimal('0')
        try:
            from apps.public_holidays.models import PublicHoliday
            hq = PublicHoliday.objects.filter(
                date__gte=s_start,
                date__lte=s_end,
            )
            if location:
                hq = hq.filter(location=location)
            for h in hq:
                if h.date.weekday() < 5:  # only count weekday holidays
                    holidays += Decimal('1')
        except Exception:
            logger.debug("Could not query PublicHoliday — skipping.", exc_info=True)

        # 3. Confirmed leave days for the member in this sprint.
        #    LeaveDay has one row per calendar date consumed by a leave record,
        #    with is_half_day=True rows representing 0.5 days.  This is the
        #    canonical source — querying it directly avoids re-deriving what the
        #    leave service already materialised and correctly handles half-days.
        leaves = Decimal('0')
        try:
            from apps.member_leaves.models import LeaveDay
            for ld in LeaveDay.objects.filter(
                member=member,
                date__gte=s_start,
                date__lte=s_end,
            ):
                leaves += Decimal('0.5') if ld.is_half_day else Decimal('1')
        except Exception:
            logger.debug("Could not query LeaveDay — skipping.", exc_info=True)

        net = Decimal(working) - holidays - leaves

        return {
            'working_days': Decimal(working),
            'holiday_days': holidays,
            'leave_days': leaves,
            'net_capacity': max(net, Decimal('0')),
        }

    @staticmethod
    def regenerate_for_sprint(sprint):
        """Rebuild capacity rows for all active team members in this sprint."""
        try:
            from apps.team_members.models import TeamMember
            members = TeamMember.objects.filter(is_active=True)
        except Exception:
            logger.warning("Cannot import TeamMember — skipping capacity rebuild.")
            return

        for member in members:
            SprintCapacityService._upsert(sprint, member)

    @staticmethod
    def regenerate_for_member(member):
        """Rebuild capacity rows for this member across all sprints."""
        from apps.sprints.models import Sprint
        for sprint in Sprint.objects.all():
            SprintCapacityService._upsert(sprint, member)

    @staticmethod
    def regenerate_for_holiday(holiday, old_date=None, old_location=None):
        """
        Rebuild capacity for members at the same location as the holiday,
        for any sprint whose window includes the holiday date.
        """
        try:
            from apps.team_members.models import TeamMember
            members = TeamMember.objects.filter(
                is_active=True,
                location=holiday.location,
            )
        except Exception:
            logger.warning("Cannot query members for holiday — skipping.")
            return

        new_date = holiday.date
        new_location = holiday.location

        from django.db.models import Q
        location_filter = Q(location=new_location)
        if old_location is not None and old_location != new_location:
            location_filter |= Q(location=old_location)
        members = list(TeamMember.objects.filter(is_active=True).filter(location_filter))

        if not members:
            return

        # ── Sprints ────────────────────────────────────────────────────────
        # Find sprints covering either the new date or the old date so both
        # the "incoming" and "outgoing" sprint windows are recalculated.
        date_filter = (
            Q(start_date__lte=new_date, end_date__gte=new_date)
        )
        if old_date is not None and old_date != new_date:
            date_filter |= Q(start_date__lte=old_date, end_date__gte=old_date)

        from apps.sprints.models import Sprint
        sprints = Sprint.objects.filter(date_filter)

        for sprint in sprints:
            for member in members:
                SprintCapacityService._upsert(sprint, member)

    @staticmethod
    def regenerate_for_leave(leave, old_start=None, old_end=None):
        """Rebuild capacity for the affected member across overlapping sprints."""
        member = leave.member
        from apps.sprints.models import Sprint

        effective_start = leave.start_date
        effective_end = leave.end_date

        if old_start is not None and old_end is not None:
            effective_start = min(effective_start, old_start)
            effective_end = max(effective_end, old_end)
        sprints = Sprint.objects.filter(
            start_date__lte=effective_end,
            end_date__gte=effective_start,
        )
        for sprint in sprints:
            SprintCapacityService._upsert(sprint, member)

    @staticmethod
    def _upsert(sprint, member):
        vals = SprintCapacityService._compute(sprint, member)
        SprintCapacity.objects.update_or_create(
            sprint=sprint,
            team_member=member,
            defaults=vals,
        )

    @staticmethod
    def list_capacity(filters=None, page=1, page_size=50):
        """
        Flexible list supporting all specified scenarios:
          - all rows
          - filtered by fy_id
          - filtered by sprint_id
          - filtered by team_id + fy_id or sprint_id
          - filtered by member_id + fy_id or sprint_id
        """
        qs = SprintCapacity.objects.select_related(
            'sprint',
            'sprint__financial_year',
            'team_member',
            'team_member__team',
            'team_member__location',
        )

        if filters:
            if filters.get('sprint_id'):
                qs = qs.filter(sprint_id=filters['sprint_id'])
            if filters.get('fy_id'):
                qs = qs.filter(sprint__financial_year_id=filters['fy_id'])
            if filters.get('team_id'):
                qs = qs.filter(team_member__team_id=filters['team_id'])
            if filters.get('member_id'):
                qs = qs.filter(team_member_id=filters['member_id'])

        qs = qs.order_by('sprint__financial_year', 'sprint__sprint_number', 'team_member__last_name')

        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            'results': page_obj.object_list,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'page_size': page_size,
        }

    @staticmethod
    def rebuild_all():
        """Full rebuild — use sparingly (management command / admin action)."""
        from apps.team_members.models import TeamMember
        from apps.sprints.models import Sprint
        members = list(TeamMember.objects.filter(is_active=True))
        sprints = list(Sprint.objects.all())
        for sprint in sprints:
            for member in members:
                SprintCapacityService._upsert(sprint, member)
        return {'sprints': len(sprints), 'members': len(members)}
