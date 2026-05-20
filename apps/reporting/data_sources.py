"""
Curated registry of business-model tables available for Custom Reporting.
Each data source maps to a Django model and exposes a controlled set of fields.
"""
from typing import Any, Dict, List, Optional

T_TEXT     = 'text'
T_NUMBER   = 'number'
T_DATE     = 'date'
T_DATETIME = 'datetime'
T_BOOLEAN  = 'boolean'
T_CHOICE   = 'choice'


def _f(key, label, ftype, filterable=True, groupable=True, aggregatable=False, **kw):
    return {'key': key, 'label': label, 'type': ftype,
            'filterable': filterable, 'groupable': groupable, 'aggregatable': aggregatable, **kw}


DATA_SOURCES: List[Dict[str, Any]] = [

    # ── Users & Auth ──────────────────────────────────────────────────────────
    {
        'key': 'user_groups', 'label': 'User Groups', 'app_label': 'auth',
        'model': 'django.contrib.auth.models.Group',
        'fields': [
            _f('id',   'ID',   T_NUMBER,  groupable=False, aggregatable=True),
            _f('name', 'Name', T_TEXT),
        ],
    },
    {
        'key': 'users', 'label': 'Users', 'app_label': 'auth',
        'model': 'django.contrib.auth.models.User',
        'fields': [
            _f('id',          'ID',           T_NUMBER,   groupable=False, aggregatable=True),
            _f('username',    'Username',     T_TEXT),
            _f('email',       'Email',        T_TEXT),
            _f('first_name',  'First Name',   T_TEXT),
            _f('last_name',   'Last Name',    T_TEXT),
            _f('is_active',   'Active',       T_BOOLEAN),
            _f('is_staff',    'Staff',        T_BOOLEAN),
            _f('date_joined', 'Date Joined',  T_DATETIME, groupable=False),
            _f('last_login',  'Last Login',   T_DATETIME, groupable=False),
        ],
    },

    # ── Delivery Teams ────────────────────────────────────────────────────────
    {
        'key': 'teams', 'label': 'Delivery Teams', 'app_label': 'delivery_teams',
        'model': 'apps.delivery_teams.models.DeliveryTeam',
        'fields': [
            _f('id',           'ID',           T_NUMBER,   groupable=False, aggregatable=True),
            _f('name',         'Team Name',    T_TEXT),
            _f('description',  'Description',  T_TEXT,     groupable=False),
            _f('is_active',    'Active',       T_BOOLEAN),
            _f('member_count', 'Member Count', T_NUMBER,   groupable=False, aggregatable=True),
            _f('created_at',   'Created At',   T_DATETIME, groupable=False),
            _f('updated_at',   'Updated At',   T_DATETIME, groupable=False),
        ],
    },

    # ── Team Members ──────────────────────────────────────────────────────────
    {
        'key': 'team_members', 'label': 'Team Members', 'app_label': 'team_members',
        'model': 'apps.team_members.models.TeamMember',
        'fields': [
            _f('id',                    'ID',               T_NUMBER,   groupable=False, aggregatable=True),
            _f('display_name',          'Name',             T_TEXT),
            _f('email_address',         'Email',            T_TEXT,     groupable=False),
            _f('role__role',            'Role',             T_TEXT),
            _f('employment_type__name', 'Employment Type',  T_TEXT),
            _f('location__city',        'Location (City)',  T_TEXT),
            _f('location__country',     'Location (Country)', T_TEXT),
            _f('start_date',            'Start Date',       T_DATE,     groupable=False),
            _f('end_date',              'End Date',         T_DATE,     groupable=False),
            _f('default_holidays',      'Default Holidays', T_NUMBER,   groupable=False, aggregatable=True),
            _f('is_active',             'Active',           T_BOOLEAN),
            _f('created_at',            'Created At',       T_DATETIME, groupable=False),
        ],
    },

    # ── Business Units ────────────────────────────────────────────────────────
    {
        'key': 'business_units', 'label': 'Business Units', 'app_label': 'business_units',
        'model': 'apps.business_units.models.BusinessUnit',
        'fields': [
            _f('id',         'ID',         T_NUMBER,   groupable=False, aggregatable=True),
            _f('full_name',  'Full Name',  T_TEXT),
            _f('short_name', 'Short Name', T_TEXT),
            _f('is_active',  'Active',     T_BOOLEAN),
            _f('created_at', 'Created At', T_DATETIME, groupable=False),
            _f('updated_at', 'Updated At', T_DATETIME, groupable=False),
        ],
    },

    # ── Programmes ────────────────────────────────────────────────────────────
    {
        'key': 'programmes', 'label': 'Programmes', 'app_label': 'programmes',
        'model': 'apps.programmes.models.Programme',
        'fields': [
            _f('id',          'ID',          T_NUMBER,   groupable=False, aggregatable=True),
            _f('name',        'Name',        T_TEXT),
            _f('description', 'Description', T_TEXT,     groupable=False),
            _f('is_active',   'Active',      T_BOOLEAN),
            _f('created_at',  'Created At',  T_DATETIME, groupable=False),
            _f('updated_at',  'Updated At',  T_DATETIME, groupable=False),
        ],
    },

    # ── Projects ──────────────────────────────────────────────────────────────
    {
        'key': 'projects', 'label': 'Projects', 'app_label': 'projects',
        'model': 'apps.projects.models.Project',
        'fields': [
            _f('id',                   'ID',                T_NUMBER,   groupable=False, aggregatable=True),
            _f('name',                 'Project Name',      T_TEXT),
            _f('status',               'Status',            T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('NEW','New'),('IN_PROGRESS','In Progress'),('ON_HOLD','On Hold'),
                   ('COMPLETED','Completed'),('CANCELLED','Cancelled')]]),
            _f('sub_status__name',     'Sub-Status',        T_TEXT),
            _f('confidence',           'Confidence',        T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('VERY_HIGH','Very High')]]),
            _f('priority',             'Priority',          T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('LOW','Low'),('MEDIUM','Medium'),('HIGH','High'),('VERY_HIGH','Very High')]]),
            _f('programme__name',      'Programme',         T_TEXT),
            _f('project_type__name',   'Project Type',      T_TEXT),
            _f('assigned_team__name',  'Assigned Team',     T_TEXT),
            _f('efforts_issued',       'Efforts Issued',    T_BOOLEAN),
            _f('effort_issue_commitment_date', 'Effort Issue Date', T_DATE, groupable=False),
            _f('run_cost_applies',     'Run Cost',          T_BOOLEAN),
            _f('tentative_start_date', 'Start Date',        T_DATE,     groupable=False),
            _f('tentative_end_date',   'End Date',          T_DATE,     groupable=False),
            _f('is_active',            'Active',            T_BOOLEAN),
            _f('created_at',           'Created At',        T_DATETIME, groupable=False),
            _f('updated_at',           'Updated At',        T_DATETIME, groupable=False),
        ],
    },

    # ── Project Budgets ───────────────────────────────────────────────────────
    {
        'key': 'project_budgets', 'label': 'Project Budgets', 'app_label': 'projects',
        'model': 'apps.projects.models.ProjectBudget',
        'fields': [
            _f('id',                   'ID',                T_NUMBER,   groupable=False, aggregatable=True),
            _f('project__name',        'Project',           T_TEXT),
            _f('financial_year__short_fy', 'Financial Year',T_TEXT),
            _f('allocated_budget',     'Allocated Budget',  T_NUMBER,   groupable=False, aggregatable=True),
            _f('refined_budget',       'Refined Budget',    T_NUMBER,   groupable=False, aggregatable=True),
            _f('notes',                'Notes',             T_TEXT,     groupable=False),
            _f('created_at',           'Created At',        T_DATETIME, groupable=False),
            _f('updated_at',           'Updated At',        T_DATETIME, groupable=False),
        ],
    },

    # ── Project Comments ──────────────────────────────────────────────────────
    {
        'key': 'project_comments', 'label': 'Project Comments', 'app_label': 'projects',
        'model': 'apps.projects.models.ProjectComment',
        'fields': [
            _f('id',          'ID',         T_NUMBER,   groupable=False, aggregatable=True),
            _f('project__name','Project',   T_TEXT),
            _f('comment',     'Comment',    T_TEXT,     groupable=False),
            _f('posted_by',   'Posted By',  T_TEXT),
            _f('is_pinned',   'Pinned',     T_BOOLEAN),
            _f('created_at',  'Created At', T_DATETIME, groupable=False),
            _f('updated_at',  'Updated At', T_DATETIME, groupable=False),
        ],
    },

    # ── Project Estimates ─────────────────────────────────────────────────────
    {
        'key': 'project_estimates', 'label': 'Project Estimates', 'app_label': 'projects',
        'model': 'apps.projects.models.ProjectEstimate',
        'fields': [
            _f('id',              'ID',              T_NUMBER,  groupable=False, aggregatable=True),
            _f('project__name',   'Project',         T_TEXT),
            _f('version',         'Version',         T_NUMBER,  groupable=False, aggregatable=True),
            _f('estimate_link',   'Estimate Link',   T_TEXT,    groupable=False),
            _f('shared_by',       'Shared By',       T_TEXT),
            _f('reviewed_by',     'Reviewed By',     T_TEXT),
            _f('status',          'Status',          T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('DRAFT','Draft'),('REVIEWED','Reviewed'),('SHARED','Shared'),
                   ('APPROVED','Approved'),('SUPERSEDED','Superseded')]]),
            _f('estimate_days',   'Estimate Days',   T_NUMBER,  groupable=False, aggregatable=True),
            _f('contingency_pct', 'Contingency %',   T_NUMBER,  groupable=False, aggregatable=True),
            _f('day_rate',        'Day Rate',        T_NUMBER,  groupable=False, aggregatable=True),
            _f('is_active',       'Active',          T_BOOLEAN),
            _f('created_at',      'Created At',      T_DATETIME, groupable=False),
            _f('updated_at',      'Updated At',      T_DATETIME, groupable=False),
        ],
    },

    # ── Project Contacts ──────────────────────────────────────────────────────
    {
        'key': 'project_contacts', 'label': 'Project Contacts', 'app_label': 'projects',
        'model': 'apps.projects.models.ProjectContact',
        'fields': [
            _f('id',               'ID',             T_NUMBER,  groupable=False, aggregatable=True),
            _f('project__name',    'Project',        T_TEXT),
            _f('contact__name',    'Name',           T_TEXT),
            _f('contact__email',   'Email',          T_TEXT,    groupable=False),
            _f('role',             'Contact Type',   T_CHOICE,
               choices=[{'value': 'PROJECT','label': 'Project'},{'value': 'FINANCE','label': 'Finance'}]),
            _f('is_active',        'Active',         T_BOOLEAN),
            _f('created_at',       'Created At',     T_DATETIME, groupable=False),
            _f('updated_at',       'Updated At',     T_DATETIME, groupable=False),
        ],
    },

    # ── Financial Years ───────────────────────────────────────────────────────
    {
        'key': 'financial_years', 'label': 'Financial Years', 'app_label': 'financial_years',
        'model': 'apps.financial_years.models.FinancialYear',
        'fields': [
            _f('id',         'ID',          T_NUMBER,  groupable=False, aggregatable=True),
            _f('short_fy',   'FY (Short)',  T_TEXT),
            _f('long_fy',    'FY (Long)',   T_TEXT),
            _f('start_date', 'Start Date',  T_DATE,    groupable=False),
            _f('end_date',   'End Date',    T_DATE,    groupable=False),
            _f('span_days',  'Span Days',   T_NUMBER,  groupable=False, aggregatable=True),
            _f('is_active',  'Active',      T_BOOLEAN),
            _f('notes',      'Notes',       T_TEXT,    groupable=False),
            _f('created_at', 'Created At',  T_DATETIME, groupable=False),
            _f('updated_at', 'Updated At',  T_DATETIME, groupable=False),
        ],
    },

    # ── Sprints ───────────────────────────────────────────────────────────────
    {
        'key': 'sprints', 'label': 'Sprints', 'app_label': 'sprints',
        'model': 'apps.sprints.models.Sprint',
        'fields': [
            _f('id',                       'ID',             T_NUMBER,  groupable=False, aggregatable=True),
            _f('sprint_name',              'Sprint Name',    T_TEXT),
            _f('sprint_number',            'Sprint Number',  T_NUMBER,  aggregatable=True),
            _f('financial_year__short_fy', 'Financial Year', T_TEXT),
            _f('start_date',               'Start Date',     T_DATE,    groupable=False),
            _f('end_date',                 'End Date',       T_DATE,    groupable=False),
            _f('month',                    'Month',          T_TEXT),
            _f('is_active',                'Active',         T_BOOLEAN),
            _f('is_closed',                'Closed',         T_BOOLEAN),
            _f('is_overridden',            'Overridden',     T_BOOLEAN),
        ],
    },

    # ── Sprint Capacity ───────────────────────────────────────────────────────
    {
        'key': 'sprint_capacity', 'label': 'Sprint Capacity', 'app_label': 'sprints',
        'model': 'apps.sprint_capacity.models.SprintCapacity',
        'fields': [
            _f('id',                              'ID',                   T_NUMBER,  groupable=False, aggregatable=True),
            _f('team_member__display_name',       'Team Member',          T_TEXT),
            _f('team_member__role__role',         'Role',                 T_TEXT),
            _f('sprint__sprint_name',             'Sprint',               T_TEXT),
            _f('sprint__financial_year__short_fy','Financial Year',       T_TEXT),
            _f('sprint__month',                   'Month',                T_TEXT),
            _f('working_days',                    'Working Days',         T_NUMBER,  groupable=False, aggregatable=True),
            _f('holiday_days',                    'Holiday Days',         T_NUMBER,  groupable=False, aggregatable=True),
            _f('leave_days',                      'Leave Days',           T_NUMBER,  groupable=False, aggregatable=True),
            _f('net_capacity',                    'Net Capacity (Days)',   T_NUMBER,  groupable=False, aggregatable=True),
        ],
    },

    # ── Member Leaves ─────────────────────────────────────────────────────────
    {
        'key': 'member_leaves', 'label': 'Member Leaves', 'app_label': 'member_leaves',
        'model': 'apps.member_leaves.models.MemberLeave',
        'fields': [
            _f('id',                    'ID',            T_NUMBER,  groupable=False, aggregatable=True),
            _f('member__display_name',  'Team Member',   T_TEXT),
            _f('member__role__role',    'Role',          T_TEXT),
            _f('start_date',            'Start Date',    T_DATE,    groupable=False),
            _f('end_date',              'End Date',      T_DATE,    groupable=False),
            _f('days',                  'Days',          T_NUMBER,  groupable=False, aggregatable=True),
            _f('is_half_day',           'Half Day',      T_BOOLEAN),
            _f('half_day_period',       'Period',        T_CHOICE,
               choices=[{'value':'AM','label':'AM'},{'value':'PM','label':'PM'}]),
            _f('note',                  'Note',          T_TEXT,    groupable=False),
            _f('created_at',            'Created At',    T_DATETIME, groupable=False),
        ],
    },

    # ── Public Holidays ───────────────────────────────────────────────────────
    {
        'key': 'public_holidays', 'label': 'Public Holidays', 'app_label': 'public_holidays',
        'model': 'apps.public_holidays.models.PublicHoliday',
        'fields': [
            _f('id',               'ID',       T_NUMBER,   groupable=False, aggregatable=True),
            _f('name',             'Holiday',  T_TEXT),
            _f('date',             'Date',     T_DATE,     groupable=False),
            _f('location__city',   'City',     T_TEXT),
            _f('location__country','Country',  T_TEXT),
            _f('created_at',       'Created At', T_DATETIME, groupable=False),
        ],
    },

    # ── Skills ────────────────────────────────────────────────────────────────
    {
        'key': 'skills', 'label': 'Skills', 'app_label': 'skills',
        'model': 'apps.skills.models.Skill',
        'fields': [
            _f('id',          'ID',          T_NUMBER,  groupable=False, aggregatable=True),
            _f('skill',       'Skill Code',  T_TEXT),
            _f('description', 'Description', T_TEXT,    groupable=False),
            _f('is_active',   'Active',      T_BOOLEAN),
            _f('created_at',  'Created At',  T_DATETIME, groupable=False),
            _f('updated_at',  'Updated At',  T_DATETIME, groupable=False),
        ],
    },

    # ── Resource Plans ────────────────────────────────────────────────────────
    {
        'key': 'resource_plans', 'label': 'Resource Plans', 'app_label': 'resource_plans',
        'model': 'apps.resource_plans.models.ResourcePlan',
        'fields': [
            _f('id',                       'ID',             T_NUMBER,  groupable=False, aggregatable=True),
            _f('name',                     'Plan Name',      T_TEXT),
            _f('plan_type',                'Plan Type',      T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('FY','Financial Year'),('PROJECT','Project'),
                   ('PROGRAMME','Programme'),('TEAM','Team')]]),
            _f('financial_year__short_fy', 'Financial Year', T_TEXT),
            _f('is_active',                'Active',         T_BOOLEAN),
            _f('is_head',                  'Is Head Plan',   T_BOOLEAN),
            _f('created_at',               'Created At',     T_DATETIME, groupable=False),
            _f('updated_at',               'Updated At',     T_DATETIME, groupable=False),
        ],
    },

    # ── Resource Plan Allocations ─────────────────────────────────────────────
    {
        'key': 'resource_plan_allocations', 'label': 'Resource Plan Allocations', 'app_label': 'resource_plans',
        'model': 'apps.resource_plans.models.ResourcePlanAllocation',
        'fields': [
            _f('id',                           'ID',            T_NUMBER,  groupable=False, aggregatable=True),
            _f('project__name',                'Project',       T_TEXT),
            _f('team__name',                   'Team',          T_TEXT),
            _f('team_member__display_name',    'Team Member',   T_TEXT),
            _f('programme__name',              'Programme',     T_TEXT),
            _f('sprint__sprint_name',          'Sprint',        T_TEXT),
            _f('sprint__financial_year__short_fy', 'Fin. Year', T_TEXT),
            _f('assignment_type',              'Assignment Type', T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('ENGINEER','Engineer'),('ARCHITECT','Architect'),
                   ('ADHOC','Ad-hoc'),('INTERIM','Interim')]]),
            _f('includes_in_budget',           'In Budget',     T_BOOLEAN),
            _f('engine_days',                  'Engine Days',   T_NUMBER,  groupable=False, aggregatable=True),
            _f('override_days',                'Override Days', T_NUMBER,  groupable=False, aggregatable=True),
        ],
    },

    # ── Sprint Forecast (Imports - Forecast type) ─────────────────────────────
    {
        'key': 'sprint_forecast', 'label': 'Sprint Forecast Imports', 'app_label': 'sprint_forecast',
        'model': 'apps.sprint_forecast.models.SprintImport',
        'base_filters': [{'field': 'import_type', 'operator': 'eq', 'value': 'FORECAST'}],
        'fields': [
            _f('id',                    'ID',            T_NUMBER,   groupable=False, aggregatable=True),
            _f('sprint__sprint_name',   'Sprint',        T_TEXT),
            _f('sprint__financial_year__short_fy', 'Fin. Year', T_TEXT),
            _f('team__name',            'Team',          T_TEXT),
            _f('version_number',        'Version',       T_NUMBER,   aggregatable=True),
            _f('status',                'Status',        T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('active','Active'),('superseded','Superseded'),('confirmed','Confirmed')]]),
            _f('imported_at',           'Imported At',   T_DATETIME, groupable=False),
        ],
    },

    # ── Sprint Actuals (Imports - Actual type) ────────────────────────────────
    {
        'key': 'sprint_actuals', 'label': 'Sprint Actual Imports', 'app_label': 'sprint_forecast',
        'model': 'apps.sprint_forecast.models.SprintImport',
        'base_filters': [{'field': 'import_type', 'operator': 'eq', 'value': 'ACTUAL'}],
        'fields': [
            _f('id',                    'ID',            T_NUMBER,   groupable=False, aggregatable=True),
            _f('sprint__sprint_name',   'Sprint',        T_TEXT),
            _f('sprint__financial_year__short_fy', 'Fin. Year', T_TEXT),
            _f('team__name',            'Team',          T_TEXT),
            _f('version_number',        'Version',       T_NUMBER,   aggregatable=True),
            _f('status',                'Status',        T_CHOICE,
               choices=[{'value': v, 'label': l} for v, l in [
                   ('active','Active'),('superseded','Superseded'),('confirmed','Confirmed')]]),
            _f('imported_at',           'Imported At',   T_DATETIME, groupable=False),
        ],
    },

    # ── Sprint Confirmed Rows (Forecast & Actual) ─────────────────────────────
    {
        'key': 'sprint_confirmed_rows', 'label': 'Sprint Confirmed Rows', 'app_label': 'sprint_forecast',
        'model': 'apps.sprint_forecast.models.SprintConfirmedRow',
        'fields': [
            _f('id',                       'ID',            T_NUMBER,  groupable=False, aggregatable=True),
            _f('sprint__sprint_name',      'Sprint',        T_TEXT),
            _f('sprint__financial_year__short_fy', 'Fin. Year', T_TEXT),
            _f('team__name',               'Team',          T_TEXT),
            _f('import_type',              'Type',          T_CHOICE,
               choices=[{'value':'FORECAST','label':'Forecast'},{'value':'ACTUAL','label':'Actual'}]),
            _f('jira_id',                  'Jira ID',       T_TEXT),
            _f('title',                    'Title',         T_TEXT,    groupable=False),
            _f('assignee__display_name',   'Assignee',      T_TEXT),
            _f('days',                     'Days',          T_NUMBER,  groupable=False, aggregatable=True),
            _f('label__label',             'Label',         T_TEXT),
        ],
    },

    # ── Recharge Details ──────────────────────────────────────────────────────
    {
        'key': 'recharge_details', 'label': 'Recharge Details', 'app_label': 'sprint_forecast',
        'model': 'apps.sprint_forecast.models.RechargeDetail',
        'fields': [
            _f('id',                    'ID',            T_NUMBER,   groupable=False, aggregatable=True),
            _f('sprint__sprint_name',   'Sprint',        T_TEXT),
            _f('sprint__financial_year__short_fy', 'Fin. Year', T_TEXT),
            _f('sprint__month',         'Month',         T_TEXT),
            _f('team__name',            'Team',          T_TEXT),
            _f('assignee__display_name','Assignee',      T_TEXT),
            _f('programme__name',       'Programme',     T_TEXT),
            _f('project__name',         'Project',       T_TEXT),
            _f('type',                  'Type',          T_CHOICE,
               choices=[{'value':'FORECAST','label':'Forecast'},{'value':'ACTUAL','label':'Actual'}]),
            _f('total_days',            'Total Days',    T_NUMBER,   groupable=False, aggregatable=True),
            _f('total_cost',            'Total Cost',    T_NUMBER,   groupable=False, aggregatable=True),
            _f('created_at',            'Created At',    T_DATETIME, groupable=False),
        ],
    },

    # ── Onboarding Requests ───────────────────────────────────────────────────
    {
        'key': 'onboarding', 'label': 'Onboarding Projects', 'app_label': 'onboarding',
        'model': 'apps.onboarding.models.OnboardingRequest',
        'fields': [
            _f('id',                            'ID',              T_NUMBER,  groupable=False, aggregatable=True),
            _f('project_name',                  'Project Name',    T_TEXT),
            _f('requester_email',               'Requester Email', T_TEXT),
            _f('accountable_executive_email',   'Executive Email', T_TEXT),
            _f('requirements',                  'Requirements',    T_TEXT,    groupable=False),
            _f('tentative_start_date',          'Start Date',      T_DATE,    groupable=False),
            _f('tentative_end_date',            'End Date',        T_DATE,    groupable=False),
            _f('project_code',                  'Project Code',    T_TEXT),
            _f('risk',                          'Risk',            T_TEXT,    groupable=False),
            _f('business_unit__short_name',     'Business Unit',   T_TEXT),
            _f('project__name',                 'Linked Project',  T_TEXT),
            _f('submitted_at',                  'Submitted At',    T_DATETIME, groupable=False),
        ],
    },

    # ── Win Entries ───────────────────────────────────────────────────────────
    {
        'key': 'win_entries', 'label': 'Win Entries', 'app_label': 'wins',
        'model': 'apps.wins.models.WinEntry',
        'fields': [
            _f('id',               'ID',          T_NUMBER,  groupable=False, aggregatable=True),
            _f('title',            'Title',       T_TEXT),
            _f('team__name',       'Team',        T_TEXT),
            _f('win__week_number', 'Week Number', T_NUMBER,  aggregatable=True),
            _f('win__status',      'Win Status',  T_CHOICE,
               choices=[{'value':'open','label':'Open'},{'value':'review_complete','label':'Review Complete'}]),
            _f('description',      'Description', T_TEXT,    groupable=False),
            _f('created_at',       'Created At',  T_DATETIME, groupable=False),
        ],
    },
]

_MAP: Dict[str, Dict] = {ds['key']: ds for ds in DATA_SOURCES}


def get_data_source(key: str) -> Optional[Dict]:
    return _MAP.get(key)


def list_data_sources() -> List[Dict]:
    return [
        {'key': ds['key'], 'label': ds['label'], 'app_label': ds['app_label'], 'fields': ds['fields']}
        for ds in DATA_SOURCES
    ]


def get_field_def(ds_key: str, field_key: str) -> Optional[Dict]:
    ds = get_data_source(ds_key)
    if not ds:
        return None
    return next((f for f in ds['fields'] if f['key'] == field_key), None)
