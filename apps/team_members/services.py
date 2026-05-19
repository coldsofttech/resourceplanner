import csv
import datetime
import io
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from .models import TeamMember, TeamMemberAssignment, TeamMemberHistory, get_default_holidays

logger = logging.getLogger(__name__)


class TeamMemberService:
    @staticmethod
    def _parse_bool(val):
        if val is None:
            return None
        return val.lower() == 'true'

    @staticmethod
    def list_members(filters=None, page=1, page_size=20):
        VALID_ORDER_FIELDS = {
            'first_name', 'last_name', 'email_address', 'display_name', 'location_id',
            'employment_type_id', 'role_id', 'is_active'
        }
        qs = TeamMember.objects.select_related(
            'user', 'location', 'employment_type', 'role',
        ).prefetch_related('team_assignments__team').all()

        if filters:
            if filters.get('search'):
                s_term = filters['search']
                qs = (
                    qs.filter(first_name__icontains=s_term) |
                    qs.filter(last_name__icontains=s_term) |
                    qs.filter(email_address__icontains=s_term) |
                    qs.filter(display_name__icontains=s_term)
                )
            if filters.get('is_active') is not None:
                is_active = TeamMemberService._parse_bool(filters['is_active'])
                qs = qs.filter(is_active=is_active)
            if filters.get('team_id'):
                qs = qs.filter(team_assignments__team_id=filters['team_id']).distinct()
            if filters.get('role_id'):
                qs = qs.filter(role_id=filters['role_id'])
            if filters.get('location_id'):
                qs = qs.filter(location_id=filters['location_id'])
            if filters.get('employment_type_id'):
                qs = qs.filter(employment_type_id=filters['employment_type_id'])
            if filters.get('skill_id'):
                qs = qs.filter(skills__id=filters['skill_id']).distinct()
            if filters.get('exclude_shareable') in ('true', 'True', True):
                qs = qs.filter(role__is_shareable=False)

        order_by = filters.get('order_by') if filters else None
        order_dir = filters.get('order_dir') if filters else None
        order_field = order_by if order_by in VALID_ORDER_FIELDS else 'last_name'
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
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
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

        qs = TeamMember.objects.all()
        result = {}

        if wants("total_members"):
            result["total_members"] = qs.count()
        if wants("active_members"):
            result["active_members"] = qs.filter(is_active=True).count()
        if wants("inactive_members"):
            result["inactive_members"] = qs.filter(is_active=False).count()
        if wants("assigned_members"):
            result["assigned_members"] = (
                qs.filter(is_active=True, team_assignments__isnull=False).distinct().count()
            )
        if wants("unassigned_members"):
            result["unassigned_members"] = (
                qs.filter(is_active=True).exclude(team_assignments__isnull=False).count()
            )

        return result

    @staticmethod
    def list_options(fields=None):
        def wants(field):
            return fields is None or field in fields

        User = get_user_model()
        from apps.skills.models import Skill
        from apps.office_locations.models import OfficeLocation
        from apps.employment_types.models import EmploymentType
        from apps.team_roles.models import TeamRole
        from apps.delivery_teams.models import DeliveryTeam

        result = {}

        if wants("is_active"):
            result["is_active"] = [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ]
        if wants("skills"):
            result["skills"] = [
                {"value": s.pk, "label": s.skill}
                for s in Skill.objects.filter(is_active=True)
            ]
        if wants("locations"):
            result["locations"] = [
                {"value": loc.pk, "label": f"{loc.city}, {loc.country}", "is_default": loc.is_default}
                for loc in OfficeLocation.objects.filter(is_active=True)
            ]
        if wants("employment_types"):
            result["employment_types"] = [
                {"value": t.pk, "label": t.name, "is_default": t.is_default}
                for t in EmploymentType.objects.filter(is_active=True)
            ]
        if wants("roles"):
            result["roles"] = [
                {
                    "value": r.pk,
                    "label": r.role,
                    "is_default": r.is_default,
                    "is_assignable": r.is_assignable,
                    "is_shareable": r.is_shareable,
                }
                for r in TeamRole.objects.filter(is_active=True)
            ]
        if wants("teams"):
            result["teams"] = [
                {"value": t.pk, "label": t.name}
                for t in DeliveryTeam.objects.filter(is_active=True)
            ]
        if wants("users"):
            result["users"] = [
                {
                    "value": u.pk,
                    "label": f"{u.first_name} {u.last_name} ({u.email})".strip(),
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "email": u.email,
                }
                for u in User.objects.filter(
                    is_active=True, team_member__isnull=True
                ).order_by('last_name', 'first_name')
            ]

        return result

    @staticmethod
    def get_member(member_id: int):
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        return TeamMember.objects.select_related('user').prefetch_related(
            'team_assignments__team'
        ).get(pk=member_id)

    @staticmethod
    @transaction.atomic
    def create_member(data: dict):
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        new_user_email = (data.get('new_user_email') or '').strip().lower()
        if new_user_email:
            import secrets as _secrets
            User = get_user_model()
            new_first = (data.get('new_user_first_name') or '').strip()
            new_last = (data.get('new_user_last_name') or '').strip()
            username = new_user_email[:150]
            if User.objects.filter(username=username).exists():
                username = f'{new_user_email[:140]}{_secrets.token_hex(4)}'
            new_user = User.objects.create_user(
                username=username,
                email=new_user_email,
                first_name=new_first,
                last_name=new_last,
            )
            new_user.set_unusable_password()
            new_user.save(update_fields=['password'])
            from apps.users.models import UserProfile
            UserProfile.objects.get_or_create(
                user=new_user, defaults={'must_change_password': True}
            )
            from apps.users.utils import add_to_guest_group
            add_to_guest_group(new_user)
            data = {**dict(data), 'user': new_user}

        user = data.get('user')

        if user:
            first_name = user.first_name
            last_name = user.last_name
            email_address = user.email
            if TeamMember.objects.filter(user=user).exists():
                raise ValidationError(f"User '{email_address}' already has a team member profile.")
        else:
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            email_address = data.get('email_address', '')
            if TeamMember.objects.filter(email_address=email_address).exists():
                raise ValidationError(f"Member '{email_address}' already exists.")

        try:
            member = TeamMember(
                first_name=first_name,
                last_name=last_name,
                display_name=data.get('display_name', '').strip(),
                email_address=email_address,
                user=user,
                location=data['location'],
                employment_type=data['employment_type'],
                role=data['role'],
                start_date=data['start_date'],
                end_date=data.get('end_date') or None,
                default_holidays=data.get('default_holidays', get_default_holidays()),
                is_active=data.get('is_active', True),
            )
            member.full_clean()
            member.save()

            skills = data.get('skills', [])
            if skills:
                member.skills.set(skills)

            # Resolve team assignments.
            role = data['role']
            teams_data = data.get('teams') or []
            team_data = data.get('team')

            if teams_data:
                # Shareable role: assign to multiple teams.
                if role.is_assignable and len(teams_data) > 1:
                    raise ValidationError("Assignable roles can only be assigned to one team.")
                for team in teams_data:
                    TeamMemberAssignment.objects.create(member=member, team=team)
                if teams_data:
                    TeamMemberHistory.objects.create(
                        member=member,
                        from_team=None,
                        to_team=teams_data[0],
                        moved_on=member.start_date,
                        note='Initial team assignment',
                    )
            elif team_data:
                TeamMemberAssignment.objects.create(member=member, team=team_data)
                if role.is_assignable:
                    TeamMemberHistory.objects.create(
                        member=member,
                        from_team=None,
                        to_team=team_data,
                        moved_on=member.start_date,
                        note='Initial team assignment',
                    )

            return member
        except IntegrityError as e:
            logger.error("Database error when creating member '%s': %s", data.get('display_name'), e)
            raise ValidationError(f"Member '{data.get('display_name')}' could not be created due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when creating member '%s': %s", data.get('display_name'), e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when creating member '%s': %s", data.get('display_name'), e)
            raise

    @staticmethod
    @transaction.atomic
    def update_member(member_id: int, data: dict):
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        member = TeamMember.objects.select_related('user', 'role').prefetch_related(
            'team_assignments__team'
        ).get(pk=member_id)

        email = data.get('email_address')
        if email and not member.user_id:
            if TeamMember.objects.filter(email_address=email).exclude(pk=member_id).exists():
                raise ValidationError(f"Member '{email}' already exists.")

        old_team = member.team  # uses property

        if member.user_id:
            user_update_fields = []
            if 'first_name' in data:
                member.user.first_name = data['first_name']
                user_update_fields.append('first_name')
            if 'last_name' in data:
                member.user.last_name = data['last_name']
                user_update_fields.append('last_name')
            if user_update_fields:
                member.user.save(update_fields=user_update_fields)

        for field in ['first_name', 'last_name', 'display_name', 'email_address', 'location',
                      'employment_type', 'role', 'start_date', 'end_date', 'default_holidays', 'is_active']:
            if field == 'email_address' and member.user_id:
                continue
            if field in data:
                value = data[field]
                if field in ['first_name', 'last_name', 'display_name'] and isinstance(value, str):
                    value = value.strip()
                    if not value:
                        raise ValidationError(f"Invalid: {field} cannot be blank.")
                if field == 'email_address' and isinstance(value, str):
                    value = value.lower().strip()
                    if not value:
                        raise ValidationError(f"Invalid: {field} cannot be blank.")
                    if TeamMember.objects.filter(email_address=value).exclude(pk=member_id).exists():
                        raise ValidationError(f"Member '{value}' already exists.")
                if field == 'end_date' and not value:
                    value = None
                setattr(member, field, value)

        if ('first_name' in data or 'last_name' in data) and 'display_name' not in data:
            new_first = (member.first_name or '').strip()
            new_last = (member.last_name or '').strip()
            member.display_name = f"{new_last}, {new_first}" if new_last and new_first else new_last or new_first

        try:
            member.full_clean()
            member.save()

            if 'skills' in data:
                member.skills.set(data.get('skills') or [])

            # Handle team assignment changes.
            role = member.role
            teams_data = data.get('teams')
            team_data_present = 'team' in data
            team_data = data.get('team')

            if teams_data is not None:
                # Shareable role: replace all assignments.
                if role.is_assignable and len(teams_data) > 1:
                    raise ValidationError("Assignable roles can only be assigned to one team.")
                TeamMemberAssignment.objects.filter(member=member).delete()
                for team in teams_data:
                    TeamMemberAssignment.objects.create(member=member, team=team)
            elif team_data_present:
                # Single-team change (assignable role or form submit).
                new_team = team_data  # may be None to unassign
                if old_team != new_team:
                    TeamMemberAssignment.objects.filter(member=member).delete()
                    if new_team:
                        TeamMemberAssignment.objects.create(member=member, team=new_team)
                    if role.is_assignable:
                        TeamMemberHistory.objects.create(
                            member=member,
                            from_team=old_team,
                            to_team=new_team or None,
                            moved_on=datetime.date.today(),
                            note='Team changed' if new_team else 'Team unassigned',
                        )

            return member
        except IntegrityError as e:
            logger.error("Database error when updating member '%s': %s", member_id, e)
            raise ValidationError(f"Member '{member_id}' could not be updated due to a conflict.") from e
        except DatabaseError as e:
            logger.exception("Database error when updating member '%s': %s", member_id, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when updating member '%s': %s", member_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def delete_member(member_id: int):
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        member = TeamMember.objects.get(pk=member_id)
        try:
            member.delete()
        except DatabaseError as e:
            logger.exception("Database error when deleting member '%s': %s", member_id, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when deleting member '%s': %s", member_id, e)
            raise

    @staticmethod
    def list_leaves(member_id: int, page=1, page_size=20, include_past=False):
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        member = TeamMember.objects.select_related('location').get(pk=member_id)
        from apps.member_leaves.models import MemberLeave
        qs = MemberLeave.objects.filter(member=member).order_by('start_date')
        if not include_past:
            qs = qs.filter(end_date__gte=timezone.localdate())

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    @transaction.atomic
    def move_team(member_id: int, data: dict):
        """
        Move an is_assignable member from one team to another (replaces assignment + logs history).
        Returns 400 for is_shareable roles — use assign_team/unassign_team instead.
        """
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        if not isinstance(data, dict):
            raise ValidationError("Invalid: data must be a dictionary.")

        member = TeamMember.objects.select_related('role').prefetch_related(
            'team_assignments__team'
        ).get(pk=member_id)

        if member.role.is_shareable:
            raise ValidationError(
                "Use assign-team / unassign-team for members with shareable roles."
            )

        from_team = data.get('from_team') or None
        to_team = data.get('to_team') or None
        note = data.get('note', '').strip()

        if not note:
            if not from_team and to_team:
                note = "Initial team assignment"
            elif from_team and not to_team:
                note = "Team unassigned"

        current_team = member.team  # property — returns first assignment's team
        if current_team != from_team:
            raise ValidationError("Provided from_team does not match with member record.")
        if from_team == to_team:
            raise ValidationError("from_team and to_team cannot be same.")

        try:
            TeamMemberAssignment.objects.filter(member=member).delete()
            if to_team:
                TeamMemberAssignment.objects.create(member=member, team=to_team)

            TeamMemberHistory.objects.create(
                member=member,
                from_team=from_team,
                to_team=to_team,
                moved_on=datetime.date.today(),
                note=note,
            )
            member.save(update_fields=['updated_at'])
            return member
        except DatabaseError as e:
            logger.exception("Database error when moving member '%s': %s", member_id, e)
            raise RuntimeError("A database error occurred. Please try again later.") from e
        except Exception as e:
            logger.exception("Unexpected error when moving member '%s': %s", member_id, e)
            raise

    @staticmethod
    @transaction.atomic
    def assign_team(member_id: int, team_id: int):
        """
        Add a team assignment.
        - is_assignable roles: replaces existing assignment and logs history.
        - is_shareable roles: adds to existing assignments.
        """
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        if not team_id:
            raise ValidationError("Invalid: team_id is required.")

        member = TeamMember.objects.select_related('role').prefetch_related(
            'team_assignments__team'
        ).get(pk=member_id)

        from apps.delivery_teams.models import DeliveryTeam
        team = DeliveryTeam.objects.get(pk=team_id)

        if TeamMemberAssignment.objects.filter(member=member, team=team).exists():
            raise ValidationError(f"Member is already assigned to '{team.name}'.")

        if member.role.is_assignable:
            old_team = member.team
            TeamMemberAssignment.objects.filter(member=member).delete()
            TeamMemberHistory.objects.create(
                member=member,
                from_team=old_team,
                to_team=team,
                moved_on=datetime.date.today(),
                note='Team assigned',
            )

        TeamMemberAssignment.objects.create(member=member, team=team)
        member.save(update_fields=['updated_at'])
        return member

    @staticmethod
    @transaction.atomic
    def unassign_team(member_id: int, team_id: int):
        """Remove a team assignment."""
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        if not team_id:
            raise ValidationError("Invalid: team_id is required.")

        member = TeamMember.objects.select_related('role').get(pk=member_id)

        try:
            assignment = TeamMemberAssignment.objects.get(member=member, team_id=team_id)
        except TeamMemberAssignment.DoesNotExist:
            raise ValidationError("Member is not assigned to this team.")

        if member.role.is_assignable:
            from apps.delivery_teams.models import DeliveryTeam
            team = DeliveryTeam.objects.get(pk=team_id)
            TeamMemberHistory.objects.create(
                member=member,
                from_team=team,
                to_team=None,
                moved_on=datetime.date.today(),
                note='Team unassigned',
            )

        assignment.delete()
        member.save(update_fields=['updated_at'])
        return member

    @staticmethod
    def history(member_id: int, page=1, page_size=20):
        if not member_id:
            raise ValidationError("Invalid: member_id must be an integer and greater than 0.")
        member = TeamMember.objects.get(pk=member_id)
        qs = TeamMemberHistory.objects.filter(
            member=member
        ).select_related('from_team', 'to_team').order_by('-created_at')

        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return {
            "results": page_obj.object_list,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "page_size": page_size,
        }

    @staticmethod
    def _resolve_lookups():
        from apps.skills.models import Skill
        from apps.team_roles.models import TeamRole
        from apps.office_locations.models import OfficeLocation
        from apps.employment_types.models import EmploymentType
        from apps.delivery_teams.models import DeliveryTeam
        return {
            "role_map": {r.role.strip().lower(): r for r in TeamRole.objects.all()},
            "location_map": {
                f"{loc.city.strip().lower()}|{loc.country.strip().lower()}": loc
                for loc in OfficeLocation.objects.all()
            },
            "emp_type_map": {e.name.strip().lower(): e for e in EmploymentType.objects.all()},
            "team_map": {t.name.strip().lower(): t for t in DeliveryTeam.objects.filter(is_active=True)},
            "skill_map": {s.skill.strip().lower(): s for s in Skill.objects.filter(is_active=True)},
            "existing_emails": set(TeamMember.objects.values_list('email_address', flat=True)),
        }

    @staticmethod
    def _validate_row(row: dict, lookups: dict, default_holidays: int):
        errors = []

        first_name = row.get('first_name', '').strip()
        last_name = row.get('last_name', '').strip()
        email = row.get('email_address', '').strip().lower()
        start_date = row.get('start_date', '').strip()

        if not first_name: errors.append("'first_name' is required.")
        if not last_name:  errors.append("'last_name' is required.")
        if not email:      errors.append("'email_address' is required.")
        if not start_date: errors.append("'start_date' is required.")

        if email and email in lookups["existing_emails"]:
            errors.append(f"Email '{email}' already exists.")

        role_raw = row.get('role', '').strip()
        city_raw = row.get('city', '').strip()
        country_raw = row.get('country', '').strip()
        emp_type_raw = row.get('employment_type', '').strip()
        team_raw = row.get('team', '').strip()

        role_obj = lookups["role_map"].get(role_raw.lower()) if role_raw else None
        emp_type_obj = lookups["emp_type_map"].get(emp_type_raw.lower()) if emp_type_raw else None
        print(emp_type_obj)
        team_obj = lookups["team_map"].get(team_raw.lower()) if team_raw else None

        location_key = f"{city_raw.lower()}|{country_raw.lower()}" if city_raw and country_raw else ''
        location_obj = lookups["location_map"].get(location_key) if location_key else None

        if not role_raw:
            errors.append("'role' is required.")
        elif role_obj is None:
            errors.append(f"Role '{role_raw}' not found.")

        if not city_raw or not country_raw:
            errors.append("'location_city' and 'location_country' are both required.")
        elif location_obj is None:
            errors.append(f"Location '{city_raw}, {country_raw}' not found.")

        if not emp_type_raw:
            errors.append("'employment_type' is required.")
        elif emp_type_obj is None:
            errors.append(f"Employment type '{emp_type_raw}' not found.")

        if team_raw and team_obj is None:
            errors.append(f"Team '{team_raw}' not found.")

        display_name = row.get('display_name', '').strip()
        if not display_name:
            display_name = (
                f"{last_name}, {first_name}" if last_name and first_name
                else last_name or first_name
            )

        end_date_raw = row.get('end_date', '').strip() or None

        try:
            holidays = int(row.get('default_holidays', '').strip() or default_holidays)
        except ValueError:
            errors.append("'default_holidays' must be an integer.")
            holidays = default_holidays

        is_active_raw = (row.get('is_active') or 'true').strip().lower()
        if is_active_raw not in ('true', 'false'):
            errors.append("'is_active' must be 'true' or 'false'.")
            is_active = True
        else:
            is_active = is_active_raw == 'true'

        if errors:
            raise ValidationError(errors)

        return {
            "first_name": first_name,
            "last_name": last_name,
            "display_name": display_name,
            "email_address": email,
            "role": role_obj,
            "location": location_obj,
            "employment_type": emp_type_obj,
            "team": team_obj,
            "start_date": start_date,
            "end_date": end_date_raw,
            "default_holidays": holidays,
            "is_active": is_active,
        }

    @staticmethod
    def bulk_import(request, dry_run=False):
        from apps.configurations.services import ConfigurationService

        file = request.FILES.get("file")
        if not file:
            raise ValidationError("No file provided.")
        if not file.name.endswith(".csv"):
            raise ValidationError("Only CSV files are supported.")

        try:
            decoded = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))
            rows = list(reader)
        except UnicodeDecodeError:
            logger.warning("Unicode error when reading import file.")
            raise ValidationError("File must be UTF-8 encoded.")
        except Exception as e:
            logger.exception("Unexpected error reading import file: %s", e)
            raise

        MAX_ROWS = 500
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"Maximum {MAX_ROWS} rows allowed per import.")

        REQUIRED_HEADERS = {
            'first_name', 'last_name', 'email_address',
            'role', 'city', 'country',
            'employment_type', 'start_date',
        }
        actual_headers = set(reader.fieldnames or [])
        missing = REQUIRED_HEADERS - actual_headers
        if missing:
            raise ValidationError(f"Missing required columns: {', '.join(sorted(missing))}")

        try:
            default_holidays = int(ConfigurationService.get_int('DEFAULT_HOLIDAYS', 0))
        except (ValueError, TypeError):
            default_holidays = 0

        lookups = TeamMemberService._resolve_lookups()

        results = {
            "succeeded": [],
            "failed": [],
            "total": len(rows),
            "dry_run": dry_run,
            "summary": "",
        }

        for index, row in enumerate(rows, start=2):
            display_email = row.get('email_address', '').strip()
            try:
                cleaned = TeamMemberService._validate_row(row, lookups, default_holidays)

                if dry_run:
                    results["succeeded"].append({"row": index, "name": cleaned["display_name"]})
                else:
                    # Extract team before creating (not a direct model field).
                    team_obj = cleaned.pop('team', None)
                    member = TeamMember.objects.create(**cleaned)
                    if team_obj:
                        TeamMemberAssignment.objects.create(member=member, team=team_obj)
                        if member.role.is_assignable:
                            TeamMemberHistory.objects.create(
                                member=member,
                                from_team=None,
                                to_team=team_obj,
                                moved_on=member.start_date,
                                note='Initial team assignment',
                            )
                    lookups["existing_emails"].add(cleaned["email_address"])
                    results["succeeded"].append({"row": index, "name": member.display_name})
            except ValidationError as e:
                results["failed"].append({
                    "row": index,
                    "name": display_email,
                    "error": e.messages if hasattr(e, 'messages') else [str(e)],
                })
            except (IntegrityError, DatabaseError) as e:
                logger.exception("DB error on row %s: %s", index, e)
                results["failed"].append({
                    "row": index,
                    "name": display_email,
                    "error": ["A database error occurred for this row."],
                })
            except Exception as e:
                logger.exception("Unexpected error on row %s: %s", index, e)
                results["failed"].append({
                    "row": index,
                    "name": display_email,
                    "error": [str(e)],
                })

        results["summary"] = (
            f"Validation complete: {len(results['succeeded'])} rows valid, "
            f"{len(results['failed'])} rows have errors."
            if dry_run else
            f"{len(results['succeeded'])} imported, {len(results['failed'])} failed."
        )

        return results
