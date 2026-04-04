import csv
import datetime
import io
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .models import LeaveDay, MemberLeave

logger = logging.getLogger(__name__)


def _working_days_between(start_date: datetime.date, end_date: datetime.date, holiday_dates: set):
    """
    Count working days (Mon-Fri, not a public holiday) between start_date and
    end_date inclusive.  Returns a Decimal so callers can halve it cleanly.
    """
    count = Decimal('0')
    current = start_date
    one_day = datetime.timedelta(days=1)
    while current <= end_date:
        if current.weekday() < 5 and current not in holiday_dates:  # Mon-Fri
            count += Decimal('1')
        current += one_day
    return count


def _holiday_dates_for_member(member) -> set:
    """
    Return the set of public holiday dates that apply to the member's location.
    If the member has no location, returns an empty set.
    """
    from apps.public_holidays.models import PublicHoliday
    location = getattr(member, 'location', None)
    if location is None:
        return set()
    return set(
        PublicHoliday.objects.filter(location=location).values_list('date', flat=True)
    )


def _calculate_days(leave: MemberLeave, holiday_dates: set | None = None) -> Decimal:
    """
    Compute the decimal day count for a MemberLeave instance.
    - Half-day (is_half_day=True, start==end): 0.5 if that day is a working day else 0.
    - Full span: count Mon-Fri days excluding public holidays.
    """
    if holiday_dates is None:
        holiday_dates = _holiday_dates_for_member(leave.member)

    if leave.is_half_day:
        d = leave.start_date
        if d.weekday() < 5 and d not in holiday_dates:
            return Decimal('0.5')
        return Decimal('0')

    return _working_days_between(leave.start_date, leave.end_date, holiday_dates)


def _rebuild_leave_days(leave: MemberLeave, holiday_dates: set | None = None):
    """
    Delete and recreate all LeaveDay rows for the given MemberLeave.
    Must be called inside a transaction.
    """
    if holiday_dates is None:
        holiday_dates = _holiday_dates_for_member(leave.member)

    LeaveDay.objects.filter(leave=leave).delete()

    rows = []
    if leave.is_half_day:
        d = leave.start_date
        if d.weekday() < 5 and d not in holiday_dates:
            rows.append(LeaveDay(
                member=leave.member,
                leave=leave,
                date=d,
                is_half_day=True,
                half_day_period=leave.half_day_period,
            ))
    else:
        current = leave.start_date
        one_day = datetime.timedelta(days=1)
        while current <= leave.end_date:
            if current.weekday() < 5 and current not in holiday_dates:
                rows.append(LeaveDay(
                    member=leave.member,
                    leave=leave,
                    date=current,
                    is_half_day=False,
                    half_day_period=None,
                ))
            current += one_day

    LeaveDay.objects.bulk_create(rows, ignore_conflicts=True)


class MemberLeaveService:

    @staticmethod
    def list_leaves(filters=None, page=1, page_size=20):
        """
        Return paginated, filtered, ordered leaves.

        Filter keys: search, member_id, include_past (bool string), year,
                     order_by, order_dir
        """
        VALID_ORDER_FIELDS = {'start_date', 'end_date', 'days', 'member_id'}
        qs = MemberLeave.objects.select_related('member', 'member__location').all()

        if filters:
            if filters.get('search'):
                term = filters['search']
                qs = qs.filter(member__first_name__icontains=term) | \
                     qs.filter(member__last_name__icontains=term) | \
                     qs.filter(note__icontains=term)

            if filters.get('member_id'):
                qs = qs.filter(member_id=filters['member_id'])

            include_past_raw = str(filters.get('include_past', 'false')).lower()
            if include_past_raw != 'true':
                qs = qs.filter(end_date__gte=timezone.localdate())

            if filters.get('year'):
                try:
                    qs = qs.filter(start_date__year=int(filters['year']))
                except (ValueError, TypeError):
                    pass

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'start_date'
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)

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
    def list_stats(fields=None):
        if fields is not None:
            if isinstance(fields, str):
                fields = {fields}
            else:
                fields = set(fields)

        def wants(field):
            return fields is None or field in fields

        today = timezone.localdate()
        qs = MemberLeave.objects.all()
        result = {}

        if wants('total_leaves'):
            result['total_leaves'] = qs.count()
        if wants('upcoming_leaves'):
            result['upcoming_leaves'] = qs.filter(start_date__gte=today).count()
        if wants('active_leaves'):
            result['active_leaves'] = qs.filter(start_date__lte=today, end_date__gte=today).count()

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        from apps.team_members.models import TeamMember
        ds = {
            "members": [
                {'value': m.pk, 'label': f"{m.first_name} {m.last_name}"}
                for m in TeamMember.objects.filter(is_active=True).order_by('last_name', 'first_name')
            ],
            "half_day_period": [
                {'value': 'AM', 'label': 'Morning (AM)'},
                {'value': 'PM', 'label': 'Afternoon (PM)'},
            ]
        }
        result = {}

        if wants('members'):
            result['members'] = ds['members']
        if wants('half_day_period'):
            result['half_day_period'] = ds['half_day_period']

        return result

    @staticmethod
    def get_leave(leave_id: int):
        if not leave_id:
            raise ValidationError("Invalid: leave_id must be a positive integer.")

        return MemberLeave.objects.select_related('member', 'member__location').get(pk=leave_id)

    @staticmethod
    @transaction.atomic
    def create_leave(data: dict):
        """
        Create a MemberLeave, calculate days, and generate LeaveDay rows.
        data keys: member (TeamMember instance), start_date, end_date,
                   is_half_day (bool), half_day_period ('AM'|'PM'|None), note
        """
        if not isinstance(data, dict):
            raise ValidationError("data must be a dict.")

        member = data.get('member')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        is_half_day = bool(data.get('is_half_day', False))
        half_day_period = data.get('half_day_period') or None
        note = (data.get('note') or '').strip()

        # Overlap check — same member, overlapping date range
        overlap_qs = MemberLeave.objects.filter(member=member, start_date__lte=end_date, end_date__gte=start_date)
        if overlap_qs.exists():
            raise ValidationError(
                "This member already has a leave record that overlaps with the selected dates."
            )

        try:
            public_holidays = _holiday_dates_for_member(member)

            leave = MemberLeave(
                member=member,
                start_date=start_date,
                end_date=end_date,
                is_half_day=is_half_day,
                half_day_period=half_day_period if is_half_day else None,
                days=Decimal('0'),
                note=note,
            )
            leave.full_clean()
            leave.days = _calculate_days(leave, public_holidays)
            leave.save()
            _rebuild_leave_days(leave, public_holidays)
            return leave
        except IntegrityError as e:
            logger.error("Database error when creating leave '%s, %s, %s': %s", member.pk, start_date, end_date, e)
            raise ValidationError(
                f"Leave '{data.get('location')}, {data.get('date')}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating leave '%s, %s, %s': %s", member.pk, start_date, end_date, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating leave '%s, %s, %s': %s", member.pk, start_date, end_date,
                             e)
            raise

    @staticmethod
    @transaction.atomic
    def update_leave(leave_id: int, data: dict):
        if not leave_id:
            raise ValidationError("leave_id must be a positive integer.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        leave = MemberLeave.objects.select_related('member', 'member__location').get(pk=leave_id)
        if not leave:
            raise ValidationError(f"Leave '{leave_id}' does not exist.")

        if 'member' in data:
            leave.member = data['member']
        if 'start_date' in data:
            leave.start_date = data['start_date']
        if 'end_date' in data:
            leave.end_date = data['end_date']
        if 'is_half_day' in data:
            leave.is_half_day = bool(data['is_half_day'])
        if 'half_day_period' in data:
            leave.half_day_period = data['half_day_period'] or None
        if 'note' in data:
            leave.note = (data['note'] or '').strip()

        # Overlap check (exclude self)
        overlap_qs = MemberLeave.objects.filter(
            member=leave.member,
            start_date__lte=leave.end_date,
            end_date__gte=leave.start_date,
        ).exclude(pk=leave_id)
        if overlap_qs.exists():
            raise ValidationError(
                "This member already has a leave record that overlaps with the selected dates."
            )

        try:
            public_holidays = _holiday_dates_for_member(leave.member)
            leave.full_clean()
            leave.days = _calculate_days(leave, public_holidays)
            leave.save()
            _rebuild_leave_days(leave, public_holidays)
            return leave
        except IntegrityError as e:
            logger.error("Database error when updating leave '%s': %s", leave_id, e)
            raise ValidationError(f"Leave '{leave_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating leave '%s': %s", leave_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating leave '%s': %s", leave_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_leave(leave_id: int):
        if not leave_id:
            raise ValidationError("leave_id must be a positive integer.")

        leave = MemberLeave.objects.get(pk=leave_id)
        if not leave:
            raise ValidationError(f"Leave '{leave_id}' does not exist.")

        try:
            # LeaveDay rows are cascade-deleted by FK
            leave.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting leave '%s': %s", leave_id, e)
            raise RuntimeError(f"A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting leave '%s': %s", leave_id, e)
            raise

    @staticmethod
    def recalculate_for_location(location_id: int):
        """
        Called when a PublicHoliday is created/updated/deleted for a location.
        Recalculates days and rebuilds LeaveDay rows for every MemberLeave
        belonging to members at that location.

        Returns the number of leave records updated.
        """
        from apps.team_members.models import TeamMember
        from apps.public_holidays.models import PublicHoliday

        holiday_dates = set(
            PublicHoliday.objects.filter(location_id=location_id).values_list('date', flat=True)
        )

        members = TeamMember.objects.filter(location_id=location_id)
        leaves = MemberLeave.objects.filter(member__in=members).select_related('member', 'member__location')

        updated = 0
        for leave in leaves:
            new_days = _calculate_days(leave, holiday_dates)
            with transaction.atomic():
                leave.days = new_days
                leave.save(update_fields=['days', 'updated_at'])
                _rebuild_leave_days(leave, holiday_dates)
            updated += 1

        return updated

    @staticmethod
    def _resolve_lookups():
        from apps.team_members.models import TeamMember
        from apps.public_holidays.models import PublicHoliday

        # Key by lowercase email_address so CSV lookup is case-insensitive
        members = {
            m.email_address.lower(): m
            for m in TeamMember.objects.select_related('location').filter(is_active=True)
        }
        holidays_by_location: dict[int, set] = {}
        for h in PublicHoliday.objects.all():
            holidays_by_location.setdefault(h.location_id, set()).add(h.date)

        return {'members': members, 'holidays_by_location': holidays_by_location}

    @staticmethod
    def _validate_row(row: dict, lookups: dict):
        errors = []

        email_raw = row.get('email_address', '').strip()
        start_raw = row.get('start_date', '').strip()
        end_raw = row.get('end_date', '').strip()
        is_half_day_raw = (row.get('is_half_day') or 'false').strip().lower()
        half_day_period_raw = (row.get('half_day_period') or '').strip().upper()

        if not email_raw:
            errors.append("'email_address' is required.")
        if not start_raw:
            errors.append("'start_date' is required.")
        if not end_raw:
            errors.append("'end_date' is required.")

        member = None
        if email_raw:
            member = lookups['members'].get(email_raw.lower())
            if member is None:
                errors.append(f"No active TeamMember found with email '{email_raw}'.")

        start_date = end_date = None
        if start_raw:
            try:
                start_date = datetime.date.fromisoformat(start_raw)
            except ValueError:
                errors.append(f"'start_date' must be YYYY-MM-DD, got '{start_raw}'.")
        if end_raw:
            try:
                end_date = datetime.date.fromisoformat(end_raw)
            except ValueError:
                errors.append(f"'end_date' must be YYYY-MM-DD, got '{end_raw}'.")

        is_half_day = is_half_day_raw == 'true'
        if is_half_day:
            if start_date and end_date and start_date != end_date:
                errors.append("Half-day leave must have start_date == end_date.")
            if half_day_period_raw not in ('AM', 'PM'):
                errors.append("'half_day_period' must be AM or PM for half-day leaves.")
        else:
            half_day_period_raw = None

        if start_date and end_date and end_date < start_date:
            errors.append("'end_date' must be >= 'start_date'.")

        if errors:
            raise ValidationError(errors)

        holiday_dates = set()
        if member and member.location_id:
            holiday_dates = lookups['holidays_by_location'].get(member.location_id, set())

        leave_obj = MemberLeave(
            member=member,
            start_date=start_date,
            end_date=end_date,
            is_half_day=is_half_day,
            half_day_period=half_day_period_raw,
            days=Decimal('0'),
            note=(row.get('note') or '').strip(),
        )
        leave_obj.days = _calculate_days(leave_obj, holiday_dates)
        return leave_obj

    @staticmethod
    def bulk_import(request, dry_run=False):
        file = request.FILES.get('file')
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith('.csv'):
            raise ValidationError("Only CSV files are supported.")

        try:
            decoded = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError:
            logger.warning("Unicode error when reading import file.")
            raise ValidationError("File must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error reading import file: %s", e)
            raise

        if len(rows) > 500:
            raise ValidationError("Maximum 500 rows allowed per import.")

        REQUIRED_HEADERS = {'email_address', 'start_date', 'end_date'}
        missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"Missing required columns: {', '.join(sorted(missing))}")

        lookups = MemberLeaveService._resolve_lookups()
        results = {"succeeded": [], "failed": [], "total": len(rows), "dry_run": dry_run, "summary": ""}

        for index, row in enumerate(rows, start=2):
            label = (
                f"{row.get('email_address', '?')} "
                f"{row.get('start_date', '?')} – {row.get('end_date', '?')}"
            )
            try:
                leave_obj = MemberLeaveService._validate_row(row, lookups)
                if dry_run:
                    results['succeeded'].append({'row': index, 'name': label})
                else:
                    MemberLeaveService.create_leave({
                        'member': leave_obj.member,
                        'start_date': leave_obj.start_date,
                        'end_date': leave_obj.end_date,
                        'is_half_day': leave_obj.is_half_day,
                        'half_day_period': leave_obj.half_day_period,
                        'note': leave_obj.note,
                    })
                    results['succeeded'].append({'row': index, 'name': label})
            except ValidationError as e:
                results['failed'].append({
                    'row': index, 'name': label,
                    'error': e.messages if hasattr(e, 'messages') else [str(e)],
                })
            except (IntegrityError, DatabaseError) as e:
                logger.exception("DB error on row %s: %s", index, e)
                results['failed'].append({'row': index, 'name': label, 'error': ["A database error occurred."]})
            except Exception as e:
                logger.exception("Unexpected error on row %s: %s", index, e)
                results['failed'].append({'row': index, 'name': label, 'error': [str(e)]})

        results['summary'] = (
            f"Validation complete: {len(results['succeeded'])} rows valid, "
            f"{len(results['failed'])} rows have errors."
            if dry_run else
            f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
        )
        return results
