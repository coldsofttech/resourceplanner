import csv
import io
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum

from apps.configurations.services import ConfigurationService
from apps.projects.models import ProjectContact, ProjectLabel
from apps.sprint_capacity.models import SprintCapacity

from .models import (
    IMPORT_STATUS_ACTIVE,
    IMPORT_STATUS_CONFIRMED,
    IMPORT_STATUS_SUPERSEDED,
    IMPORT_TYPE_FORECAST,
    IMPORT_TYPE_ACTUAL,
    RECHARGE_TYPE_FORECAST,
    RECHARGE_TYPE_ACTUAL,
    CHECK_LABEL,
    CHECK_MAPPING,
    CHECK_CAPACITY,
    CHECK_PASS,
    CHECK_ERROR,
    SprintImport,
    SprintImportRow,
    ImportReview,
    ImportReviewResult,
    ProjectFinanceType,
    ProjectFinanceTypeMapping,
    ProjectActuals,
    ProjectSprintActual,
    Recharge,
    RechargeDetail,
    RechargeStory,
    SprintImportReviewComplete,
    SprintConfirmedRow,
)

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    'story_type',
    'jira_id',
    'title',
    'assignee',
    'efforts_ms',
    'sprint',
    'label',
    'mapping',
]


def _get_hours_per_day():
    return ConfigurationService.get_int('HOURS_PER_DAY', 7)


def _get_sprint_point_price():
    return ConfigurationService.get_float('SPRINT_POINT_PRICE', 0.0)


def _ms_to_days(ms, hours_per_day=None):
    if hours_per_day is None:
        hours_per_day = _get_hours_per_day()
    if not ms or ms <= 0 or hours_per_day <= 0:
        return Decimal('0.00')
    ms_per_day = hours_per_day * 3_600_000
    return (Decimal(ms) / Decimal(ms_per_day)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _match_assignee(raw):
    """Match raw assignee string to a TeamMember. Try email → display_name → fuzzy name."""
    if not raw:
        return None
    from apps.team_members.models import TeamMember
    raw_stripped = raw.strip()

    member = TeamMember.objects.filter(email_address__iexact=raw_stripped).first()
    if member:
        return member

    member = TeamMember.objects.filter(display_name__iexact=raw_stripped).first()
    if member:
        return member

    parts = raw_stripped.replace(',', ' ').split()
    if len(parts) >= 2:
        q = Q()
        for part in parts:
            q &= (Q(first_name__icontains=part) | Q(last_name__icontains=part))
        member = TeamMember.objects.filter(q).first()
        if member:
            return member
    return None


def _match_label(raw):
    if not raw:
        return None
    return ProjectLabel.objects.filter(label__iexact=raw.strip()).first()


def _match_finance_type(raw):
    if not raw:
        return None
    return ProjectFinanceType.objects.filter(code__iexact=raw.strip().upper()).first()


class SprintImportService:

    @staticmethod
    def get_next_version(sprint_id, team_id, import_type=IMPORT_TYPE_FORECAST):
        last = SprintImport.objects.filter(
            sprint_id=sprint_id, team_id=team_id, import_type=import_type
        ).order_by('-version_number').first()
        return (last.version_number + 1) if last else 1

    @staticmethod
    @transaction.atomic
    def import_csv(sprint_id, team_id, csv_file, user=None, import_type=IMPORT_TYPE_FORECAST):
        """Parse CSV, supersede previous active/confirmed import, create new SprintImport + SprintImportRow records."""
        version = SprintImportService.get_next_version(sprint_id, team_id, import_type)

        SprintImport.objects.filter(
            sprint_id=sprint_id,
            team_id=team_id,
            import_type=import_type,
            status__in=[IMPORT_STATUS_ACTIVE, IMPORT_STATUS_CONFIRMED],
        ).update(status=IMPORT_STATUS_SUPERSEDED)

        recharge_type = RECHARGE_TYPE_ACTUAL if import_type == IMPORT_TYPE_ACTUAL else RECHARGE_TYPE_FORECAST
        SprintConfirmedRow.objects.filter(sprint_id=sprint_id, team_id=team_id, import_type=import_type).delete()
        RechargeDetail.objects.filter(sprint_id=sprint_id, team_id=team_id, type=recharge_type).delete()

        sprint_import = SprintImport.objects.create(
            sprint_id=sprint_id,
            team_id=team_id,
            version_number=version,
            status=IMPORT_STATUS_ACTIVE,
            import_type=import_type,
            imported_by=user,
        )

        try:
            text = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            csv_file.seek(0)
            text = csv_file.read().decode('latin-1')

        reader = csv.DictReader(io.StringIO(text))
        detected_headers = list(reader.fieldnames or [])
        rows = []
        for order, row in enumerate(reader):
            raw = {k.strip().lower().replace('(', '').replace(')', '').replace(' ', '_').replace('/', '_').strip('_'): (v or '').strip() for k, v in row.items() if k}

            # Skip blank rows and aggregate/totals rows
            all_values = [v for v in raw.values() if v]
            if not all_values:
                continue
            mapping_probe = raw.get('mapping', raw.get('finance_type', ''))
            label_probe = raw.get('label', raw.get('labels', ''))
            if mapping_probe.upper() in ('TOTAL', 'TOTALS', 'SUBTOTAL', 'GRAND TOTAL') and not label_probe:
                continue

            story_type = raw.get('story_type', raw.get('issue_type', raw.get('issuetype', raw.get('type', ''))))
            jira_id = raw.get('jira_id', raw.get('jira', raw.get('issue_key', raw.get('key', ''))))
            title = raw.get('title_description', raw.get('title', raw.get('summary', raw.get('description', ''))))
            assignee_raw = raw.get('assignee', raw.get('assignee_name', ''))
            if 'efforts_s' in raw:
                efforts_str = raw['efforts_s']
                efforts_scale = 1000
            elif 'original_estimate' in raw:
                efforts_str = raw['original_estimate']
                efforts_scale = 1000
            else:
                efforts_str = raw.get('efforts_ms', raw.get('efforts', '0'))
                efforts_scale = 1
            sprint_name = raw.get('sprint', raw.get('sprint_name', ''))
            label_raw = raw.get('label', raw.get('labels', ''))
            mapping_raw = raw.get('mapping', raw.get('finance_type', ''))

            try:
                efforts_ms = int(float(efforts_str) * efforts_scale) if efforts_str else 0
            except (ValueError, TypeError):
                efforts_ms = 0

            assignee = _match_assignee(assignee_raw)
            label = _match_label(label_raw)
            mapping = _match_finance_type(mapping_raw)

            rows.append(SprintImportRow(
                sprint_import=sprint_import,
                order=order,
                story_type=story_type,
                jira_id=jira_id,
                title=title,
                assignee_raw=assignee_raw,
                assignee=assignee,
                efforts_ms=efforts_ms,
                sprint_name=sprint_name,
                label_raw=label_raw,
                label=label,
                mapping_raw=mapping_raw,
                mapping=mapping,
            ))

        SprintImportRow.objects.bulk_create(rows)
        sprint_import._detected_headers = detected_headers
        return sprint_import

    @staticmethod
    def list_imports(sprint_id, team_id=None, import_type=None):
        qs = SprintImport.objects.filter(sprint_id=sprint_id).select_related('team', 'imported_by')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if import_type:
            qs = qs.filter(import_type=import_type)
        return qs.order_by('team__name', 'version_number')

    @staticmethod
    def get_sprint_teams_status(sprint_id, import_type=IMPORT_TYPE_FORECAST):
        """Return status summary per team for a sprint."""
        from apps.delivery_teams.models import DeliveryTeam
        teams = DeliveryTeam.objects.filter(is_active=True).order_by('name')
        result = []
        for team in teams:
            imports = SprintImport.objects.filter(sprint_id=sprint_id, team_id=team.id, import_type=import_type)
            latest = imports.order_by('-version_number').first()
            has_imports = latest is not None
            confirmed = has_imports and latest.status == IMPORT_STATUS_CONFIRMED
            result.append({
                'team': team,
                'has_imports': has_imports,
                'confirmed': confirmed,
                'latest_import': latest,
                'versions': list(imports.order_by('version_number')),
            })
        return result


class ImportReviewService:

    @staticmethod
    @transaction.atomic
    def run_review(sprint_import_id, user=None):
        """Run all three checks against the rows of a SprintImport."""
        si = SprintImport.objects.select_related('sprint').get(pk=sprint_import_id)
        rows = list(si.rows.select_related(
            'assignee', 'assignee_override',
            'label', 'label_override',
            'mapping', 'mapping_override',
        ).order_by('order'))

        review = ImportReview.objects.create(sprint_import=si, reviewed_by=user)
        results = []

        valid_labels = set(ProjectLabel.objects.values_list('label', flat=True))
        ft_map = {}
        for ftm in ProjectFinanceTypeMapping.objects.select_related('finance_type'):
            ft_map.setdefault(ftm.project_type_id, set()).add(ftm.finance_type_id)
        ft_by_id = {ft.id: ft for ft in ProjectFinanceType.objects.all()}

        member_days = {}
        hours_per_day = _get_hours_per_day()

        for row in rows:
            eff_label = row.effective_label
            eff_mapping = row.effective_mapping
            eff_assignee = row.effective_assignee
            eff_jira_id = row.effective_jira_id

            # ── Check 1: label exists globally ───────────────────────────────
            if eff_label and eff_label.label in valid_labels:
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_LABEL, status=CHECK_PASS,
                    message='',
                ))
            else:
                raw = row.label_override if row.label_override else row.label_raw
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_LABEL, status=CHECK_ERROR,
                    message=f'Label "{raw}" not found in any project labels.',
                ))

            # ── Check 2: mapping valid for project type ───────────────────────
            raw_mapping_code = (row.mapping_override.code if row.mapping_override else row.mapping_raw) or ''
            if not eff_mapping:
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_MAPPING, status=CHECK_ERROR,
                    message=f'Finance type "{raw_mapping_code}" not found. Add it at Finance Types settings.',
                ))
            elif not (eff_label and eff_label.project):
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_MAPPING, status=CHECK_ERROR,
                    message='Label is not linked to a project; cannot validate mapping.',
                ))
            elif not eff_label.project.project_type_id:
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_MAPPING, status=CHECK_ERROR,
                    message=f'Project "{eff_label.project.name}" has no Project Type assigned.',
                ))
            else:
                pt_id = eff_label.project.project_type_id
                allowed = ft_map.get(pt_id, set())
                if eff_mapping.id in allowed:
                    results.append(ImportReviewResult(
                        review=review, row=row,
                        check_type=CHECK_MAPPING, status=CHECK_PASS,
                        message='',
                    ))
                else:
                    allowed_codes = sorted(
                        ft_by_id[fid].code for fid in allowed if fid in ft_by_id
                    )
                    expected = ', '.join(allowed_codes) if allowed_codes else '(none configured)'
                    results.append(ImportReviewResult(
                        review=review, row=row,
                        check_type=CHECK_MAPPING, status=CHECK_ERROR,
                        message=f'Finance type should be "{expected}" for project "{eff_label.project.name}".',
                    ))

            # ── Jira ID required (unless mapping is HOLIDAY) ──────────────────
            mapping_code = eff_mapping.code if eff_mapping else ''
            if mapping_code != 'HOLIDAY' and not eff_jira_id:
                results.append(ImportReviewResult(
                    review=review, row=row,
                    check_type=CHECK_LABEL, status=CHECK_ERROR,
                    message='Jira ID is required for non-HOLIDAY rows.',
                ))

            # ── Accumulate days for capacity check ────────────────────────────
            if eff_assignee:
                days = row.compute_days(hours_per_day)
                member_days.setdefault(eff_assignee.id, {'member': eff_assignee, 'days': Decimal('0.00')})
                member_days[eff_assignee.id]['days'] += days

        # ── Check 3: per-engineer capacity ────────────────────────────────────
        sprint_capacities = {
            sc.team_member_id: sc.net_capacity
            for sc in SprintCapacity.objects.filter(sprint_id=si.sprint_id)
        }

        capacity_results_by_member = {}
        for member_id, info in member_days.items():
            net_cap = sprint_capacities.get(member_id, Decimal('0.00'))
            total = info['days']
            if total == net_cap:
                status = CHECK_PASS
                msg = ''
            else:
                status = CHECK_ERROR
                msg = (
                    f'{info["member"].display_name}: total allocated {total}d '
                    f'≠ sprint net capacity {net_cap}d.'
                )
            capacity_results_by_member[member_id] = (status, msg)

        for row in rows:
            eff_assignee = row.effective_assignee
            if eff_assignee and eff_assignee.id in capacity_results_by_member:
                st, msg = capacity_results_by_member[eff_assignee.id]
            elif eff_assignee:
                st, msg = CHECK_ERROR, f'{eff_assignee.display_name}: no sprint capacity record found.'
            else:
                st, msg = CHECK_ERROR, 'Assignee not matched to a team member.'
            results.append(ImportReviewResult(
                review=review, row=row,
                check_type=CHECK_CAPACITY, status=st, message=msg,
            ))

        ImportReviewResult.objects.bulk_create(results)
        return review


class ImportConfirmService:

    @staticmethod
    @transaction.atomic
    def confirm(sprint_import_id, user=None):
        """
        Confirm a version:
        - Reject if no review has been run or any label/mapping check is failing
        - Mark import as confirmed
        - Delete any previously confirmed rows for this sprint+team+type
        - Write SprintConfirmedRow records
        - Write RechargeDetail records
        """
        si = SprintImport.objects.select_related('sprint', 'team').get(pk=sprint_import_id)

        latest_review = si.reviews.order_by('-reviewed_at').first()
        if not latest_review:
            raise ValueError('No review has been run. Run a review before confirming.')

        failing = latest_review.results.filter(
            check_type__in=[CHECK_LABEL, CHECK_MAPPING],
            status=CHECK_ERROR,
        )
        if failing.exists():
            raise ValueError(
                f'Cannot confirm: {failing.count()} row(s) have failing label or mapping checks. '
                f'Fix the issues and re-run the review before confirming.'
            )
        hours_per_day = _get_hours_per_day()
        price = Decimal(str(_get_sprint_point_price()))
        recharge_type = RECHARGE_TYPE_ACTUAL if si.import_type == IMPORT_TYPE_ACTUAL else RECHARGE_TYPE_FORECAST

        si.status = IMPORT_STATUS_CONFIRMED
        si.save(update_fields=['status'])

        SprintConfirmedRow.objects.filter(sprint_id=si.sprint_id, team_id=si.team_id, import_type=si.import_type).delete()
        RechargeDetail.objects.filter(sprint_id=si.sprint_id, team_id=si.team_id, type=recharge_type).delete()

        rows = list(si.rows.select_related(
            'assignee', 'assignee_override',
            'label__project__programme',
            'label_override', 'label_override__project__programme',
            'mapping', 'mapping_override',
        ).order_by('order'))

        confirmed_rows = []
        for row in rows:
            days = row.compute_days(hours_per_day)
            confirmed_rows.append(SprintConfirmedRow(
                sprint_id=si.sprint_id,
                team_id=si.team_id,
                sprint_import=si,
                import_type=si.import_type,
                story_type=row.effective_story_type,
                jira_id=row.effective_jira_id,
                title=row.effective_title,
                assignee=row.effective_assignee,
                assignee_raw=row.effective_assignee_raw,
                efforts_ms=row.effective_efforts_ms,
                days=days,
                sprint_name=row.effective_sprint_name,
                label=row.effective_label,
                label_raw=row.label_override.label if row.label_override else row.label_raw,
                mapping=row.effective_mapping,
                mapping_raw=row.mapping_override.code if row.mapping_override else row.mapping_raw,
                is_override=row.has_overrides,
            ))
        SprintConfirmedRow.objects.bulk_create(confirmed_rows)

        # Build RechargeDetail: group by (assignee, project, programme, label)
        detail_map = {}
        for row in rows:
            eff_assignee = row.effective_assignee
            eff_label = row.effective_label
            project = eff_label.project if eff_label else None
            programme = project.programme if project else None
            days = row.compute_days(hours_per_day)
            cost = (days * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            key = (
                getattr(eff_assignee, 'id', None),
                getattr(project, 'id', None),
                getattr(programme, 'id', None),
                getattr(eff_label, 'id', None),
            )
            if key not in detail_map:
                detail_map[key] = {
                    'assignee': eff_assignee,
                    'project': project,
                    'programme': programme,
                    'label': eff_label,
                    'total_days': Decimal('0.00'),
                    'total_cost': Decimal('0.00'),
                }
            detail_map[key]['total_days'] += days
            detail_map[key]['total_cost'] += cost

        details = []
        for info in detail_map.values():
            details.append(RechargeDetail(
                sprint_id=si.sprint_id,
                team_id=si.team_id,
                assignee=info['assignee'],
                programme=info['programme'],
                project=info['project'],
                label=info['label'],
                type=recharge_type,
                total_days=info['total_days'],
                total_cost=info['total_cost'],
                sprint_import=si,
            ))
        RechargeDetail.objects.bulk_create(details)

        return si


class ImportReviewCompleteService:

    @staticmethod
    def check_warnings(sprint_id, import_type=IMPORT_TYPE_FORECAST):
        """Return list of warning strings. Empty list = no warnings."""
        from apps.delivery_teams.models import DeliveryTeam
        teams = DeliveryTeam.objects.filter(is_active=True)
        sprint_capacities = {
            sc.team_member_id: sc.net_capacity
            for sc in SprintCapacity.objects.filter(sprint_id=sprint_id)
        }
        label = 'actual' if import_type == IMPORT_TYPE_ACTUAL else 'forecast'
        warnings = []

        for team in teams:
            imports = SprintImport.objects.filter(sprint_id=sprint_id, team_id=team.id, import_type=import_type)
            if not imports.exists():
                warnings.append(f'Team "{team.name}" has no {label} imports.')
                continue
            if not imports.filter(status=IMPORT_STATUS_CONFIRMED).exists():
                warnings.append(f'Team "{team.name}" has no confirmed {label} import version.')

        confirmed_rows = SprintConfirmedRow.objects.filter(
            sprint_id=sprint_id, import_type=import_type,
        ).select_related('assignee')
        member_days = {}
        for row in confirmed_rows:
            if row.assignee_id:
                member_days.setdefault(row.assignee_id, {'name': row.assignee.display_name, 'days': Decimal('0.00')})
                member_days[row.assignee_id]['days'] += row.days

        for member_id, info in member_days.items():
            net_cap = sprint_capacities.get(member_id, Decimal('0.00'))
            if info['days'] < net_cap:
                warnings.append(
                    f'{info["name"]}: total allocated {info["days"]}d < sprint net capacity {net_cap}d.'
                )

        return warnings

    @staticmethod
    @transaction.atomic
    def complete(sprint_id, user=None, override=False, override_notes='', import_type=IMPORT_TYPE_FORECAST):
        """Mark sprint review as complete and write Recharge aggregate records."""
        SprintImportReviewComplete.objects.update_or_create(
            sprint_id=sprint_id,
            import_type=import_type,
            defaults={
                'completed_by': user,
                'override_applied': override,
                'override_notes': override_notes,
            },
        )
        ImportReviewCompleteService._write_recharges(sprint_id, import_type=import_type)

    @staticmethod
    def _write_recharges(sprint_id, import_type=IMPORT_TYPE_FORECAST):
        """Aggregate confirmed SprintConfirmedRows into Recharge + RechargeStory records."""
        price = Decimal(str(_get_sprint_point_price()))
        recharge_type = RECHARGE_TYPE_ACTUAL if import_type == IMPORT_TYPE_ACTUAL else RECHARGE_TYPE_FORECAST

        Recharge.objects.filter(sprint_id=sprint_id, type=recharge_type).delete()

        rows = list(SprintConfirmedRow.objects.filter(
            sprint_id=sprint_id, import_type=import_type,
        ).select_related(
            'label__project__programme',
            'mapping',
        ))

        agg = {}
        for row in rows:
            project = row.label.project if row.label else None
            programme = project.programme if project else None

            key = (
                getattr(programme, 'id', None),
                getattr(project, 'id', None),
            )
            if key not in agg:
                agg[key] = {
                    'programme': programme,
                    'project': project,
                    'total_days': Decimal('0.00'),
                    'total_cost': Decimal('0.00'),
                    'stories': {},
                }
            days = row.days
            cost = (days * price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            agg[key]['total_days'] += days
            agg[key]['total_cost'] += cost

            jira_key = row.jira_id or ''
            if jira_key not in agg[key]['stories']:
                agg[key]['stories'][jira_key] = {'title': row.title, 'days': Decimal('0.00')}
            agg[key]['stories'][jira_key]['days'] += days

        for info in agg.values():
            project = info['project']
            recharge = Recharge.objects.create(
                sprint_id=sprint_id,
                type=recharge_type,
                programme=info['programme'],
                project=project,
                total_days=info['total_days'],
                total_cost=info['total_cost'],
            )

            if project:
                finance_contacts = ProjectContact.objects.filter(
                    project=project, role='FINANCE', is_active=True
                )
                project_contacts = ProjectContact.objects.filter(
                    project=project, role='PROJECT', is_active=True
                )
                recharge.finance_contacts.set(finance_contacts)
                recharge.project_contacts.set(project_contacts)

            story_objs = []
            for jira_id, sinfo in info['stories'].items():
                story_objs.append(RechargeStory(
                    recharge=recharge,
                    jira_id=jira_id,
                    title=sinfo['title'],
                    total_days=sinfo['days'],
                ))
            RechargeStory.objects.bulk_create(story_objs)


class ProjectActualsService:

    @staticmethod
    @transaction.atomic
    def update_for_sprint(sprint_id):
        """Called when a sprint is closed. Creates/updates ProjectActuals + ProjectSprintActual."""
        from apps.sprints.models import Sprint

        sprint = Sprint.objects.get(pk=sprint_id)

        recharges = Recharge.objects.filter(
            sprint_id=sprint_id,
            type=RECHARGE_TYPE_ACTUAL,
        ).select_related(
            'project__programme',
            'project__assigned_team',
        )

        for recharge in recharges:
            project = recharge.project
            if not project:
                continue

            pa, _ = ProjectActuals.objects.get_or_create(project=project)

            pa.programme = project.programme
            pa.assigned_team = project.assigned_team

            primary_label = project.labels.filter(is_primary=True).first() or project.labels.first()
            pa.label = primary_label

            latest_code = project.codes.first()
            pa.code = latest_code.code if latest_code else ''

            active_estimate = project.estimates.filter(is_active=True).first()
            if active_estimate:
                base = active_estimate.estimate_days * active_estimate.day_rate
                with_contingency = base * (1 + active_estimate.contingency_pct / Decimal('100'))
                pa.estimate_value = base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                pa.estimate_value_with_contingency = with_contingency.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            pa.last_updated_sprint = sprint
            pa.save()

            collaborator_team_ids = list(
                project.project_collaborators.values_list('team_id', flat=True)
            )
            pa.collaborators.set(collaborator_team_ids)

            ProjectSprintActual.objects.update_or_create(
                project_actuals=pa,
                sprint=sprint,
                defaults={
                    'total_cost': recharge.total_cost,
                    'total_days': recharge.total_days,
                },
            )

            from django.db.models import Sum
            total = pa.sprint_actuals.aggregate(s=Sum('total_cost'))['s'] or Decimal('0')
            pa.total_cost_till_date = total
            pa.save(update_fields=['total_cost_till_date'])
