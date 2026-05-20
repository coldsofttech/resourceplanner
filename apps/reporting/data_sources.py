"""
Curated registry of business-model tables and columns available for Custom Reporting.
Each data source maps to a Django model and exposes a controlled set of fields.
"""
from typing import Any, Dict, List, Optional

T_TEXT     = 'text'
T_NUMBER   = 'number'
T_DATE     = 'date'
T_DATETIME = 'datetime'
T_BOOLEAN  = 'boolean'
T_CHOICE   = 'choice'

DATA_SOURCES: List[Dict[str, Any]] = [
    {
        'key':       'teams',
        'label':     'Delivery Teams',
        'app_label': 'delivery_teams',
        'model':     'apps.delivery_teams.models.DeliveryTeam',
        'fields': [
            {'key': 'id',           'label': 'ID',           'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'name',         'label': 'Team Name',    'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'is_active',    'label': 'Active',       'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'member_count', 'label': 'Member Count', 'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'created_at',   'label': 'Created At',   'type': T_DATETIME,'filterable': True, 'groupable': False, 'aggregatable': False},
        ],
    },
    {
        'key':       'team_members',
        'label':     'Team Members',
        'app_label': 'team_members',
        'model':     'apps.team_members.models.TeamMember',
        'fields': [
            {'key': 'id',                    'label': 'ID',              'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'display_name',          'label': 'Name',            'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'email_address',         'label': 'Email',           'type': T_TEXT,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'role__role',            'label': 'Role',            'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'employment_type__name', 'label': 'Employment Type', 'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'location__city',        'label': 'Location',        'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'start_date',            'label': 'Start Date',      'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'end_date',              'label': 'End Date',        'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'default_holidays',      'label': 'Default Holidays','type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'is_active',             'label': 'Active',          'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
        ],
    },
    {
        'key':       'projects',
        'label':     'Projects',
        'app_label': 'projects',
        'model':     'apps.projects.models.Project',
        'fields': [
            {'key': 'id',                   'label': 'ID',            'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'name',                 'label': 'Project Name',  'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'status',               'label': 'Status',        'type': T_CHOICE,  'filterable': True, 'groupable': True,  'aggregatable': False,
             'choices': [
                 {'value': 'NEW', 'label': 'New'}, {'value': 'IN_PROGRESS', 'label': 'In Progress'},
                 {'value': 'ON_HOLD', 'label': 'On Hold'}, {'value': 'COMPLETED', 'label': 'Completed'},
                 {'value': 'CANCELLED', 'label': 'Cancelled'},
             ]},
            {'key': 'confidence',           'label': 'Confidence',    'type': T_CHOICE,  'filterable': True, 'groupable': True,  'aggregatable': False,
             'choices': [
                 {'value': 'LOW', 'label': 'Low'}, {'value': 'MEDIUM', 'label': 'Medium'},
                 {'value': 'HIGH', 'label': 'High'}, {'value': 'VERY_HIGH', 'label': 'Very High'},
             ]},
            {'key': 'priority',             'label': 'Priority',      'type': T_CHOICE,  'filterable': True, 'groupable': True,  'aggregatable': False,
             'choices': [
                 {'value': 'LOW', 'label': 'Low'}, {'value': 'MEDIUM', 'label': 'Medium'},
                 {'value': 'HIGH', 'label': 'High'}, {'value': 'VERY_HIGH', 'label': 'Very High'},
             ]},
            {'key': 'programme__name',      'label': 'Programme',     'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'project_type__name',   'label': 'Project Type',  'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'assigned_team__name',  'label': 'Assigned Team', 'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'run_cost_applies',     'label': 'Run Cost',      'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'efforts_issued',       'label': 'Efforts Issued','type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'is_active',            'label': 'Active',        'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'tentative_start_date', 'label': 'Start Date',    'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'tentative_end_date',   'label': 'End Date',      'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'created_at',           'label': 'Created At',    'type': T_DATETIME,'filterable': True, 'groupable': False, 'aggregatable': False},
        ],
    },
    {
        'key':       'programmes',
        'label':     'Programmes',
        'app_label': 'programmes',
        'model':     'apps.programmes.models.Programme',
        'fields': [
            {'key': 'id',         'label': 'ID',         'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'name',       'label': 'Name',       'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'is_active',  'label': 'Active',     'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'created_at', 'label': 'Created At', 'type': T_DATETIME,'filterable': True, 'groupable': False, 'aggregatable': False},
        ],
    },
    {
        'key':       'sprints',
        'label':     'Sprints',
        'app_label': 'sprints',
        'model':     'apps.sprints.models.Sprint',
        'fields': [
            {'key': 'id',                      'label': 'ID',             'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'sprint_name',             'label': 'Sprint Name',    'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'sprint_number',           'label': 'Sprint Number',  'type': T_NUMBER,  'filterable': True, 'groupable': True,  'aggregatable': True},
            {'key': 'financial_year__short_fy','label': 'Financial Year', 'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'start_date',              'label': 'Start Date',     'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'end_date',                'label': 'End Date',       'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'month',                   'label': 'Month',          'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'is_active',               'label': 'Active',         'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'is_closed',               'label': 'Closed',         'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
        ],
    },
    {
        'key':       'sprint_capacity',
        'label':     'Sprint Capacity',
        'app_label': 'sprints',
        'model':     'apps.sprint_capacity.models.SprintCapacity',
        'fields': [
            {'key': 'id',                             'label': 'ID',                  'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'team_member__display_name',      'label': 'Team Member',         'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'sprint__sprint_name',            'label': 'Sprint',              'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'sprint__financial_year__short_fy','label': 'Financial Year',     'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'sprint__month',                  'label': 'Month',               'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'working_days',                   'label': 'Working Days',        'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'holiday_days',                   'label': 'Holiday Days',        'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'leave_days',                     'label': 'Leave Days',          'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'net_capacity',                   'label': 'Net Capacity (Days)', 'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
        ],
    },
    {
        'key':       'member_leaves',
        'label':     'Member Leaves',
        'app_label': 'member_leaves',
        'model':     'apps.member_leaves.models.MemberLeave',
        'fields': [
            {'key': 'id',                   'label': 'ID',          'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'member__display_name', 'label': 'Team Member', 'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'start_date',           'label': 'Start Date',  'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'end_date',             'label': 'End Date',    'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'days',                 'label': 'Days',        'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'is_half_day',          'label': 'Half Day',    'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'created_at',           'label': 'Created At',  'type': T_DATETIME,'filterable': True, 'groupable': False, 'aggregatable': False},
        ],
    },
    {
        'key':       'win_entries',
        'label':     'Win Entries',
        'app_label': 'wins',
        'model':     'apps.wins.models.WinEntry',
        'fields': [
            {'key': 'id',               'label': 'ID',          'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'title',            'label': 'Title',       'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'team__name',       'label': 'Team',        'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'win__week_number', 'label': 'Week Number', 'type': T_NUMBER,  'filterable': True, 'groupable': True,  'aggregatable': True},
            {'key': 'created_at',       'label': 'Created At',  'type': T_DATETIME,'filterable': True, 'groupable': False, 'aggregatable': False},
        ],
    },
    {
        'key':       'financial_years',
        'label':     'Financial Years',
        'app_label': 'financial_years',
        'model':     'apps.financial_years.models.FinancialYear',
        'fields': [
            {'key': 'id',         'label': 'ID',          'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
            {'key': 'short_fy',   'label': 'FY (Short)',  'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'long_fy',    'label': 'FY (Long)',   'type': T_TEXT,    'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'start_date', 'label': 'Start Date',  'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'end_date',   'label': 'End Date',    'type': T_DATE,    'filterable': True, 'groupable': False, 'aggregatable': False},
            {'key': 'is_active',  'label': 'Active',      'type': T_BOOLEAN, 'filterable': True, 'groupable': True,  'aggregatable': False},
            {'key': 'span_days',  'label': 'Span Days',   'type': T_NUMBER,  'filterable': True, 'groupable': False, 'aggregatable': True},
        ],
    },
]

_MAP: Dict[str, Dict] = {ds['key']: ds for ds in DATA_SOURCES}


def get_data_source(key: str) -> Optional[Dict]:
    return _MAP.get(key)


def list_data_sources() -> List[Dict]:
    return [{'key': ds['key'], 'label': ds['label'], 'app_label': ds['app_label'], 'fields': ds['fields']} for ds in DATA_SOURCES]


def get_field_def(ds_key: str, field_key: str) -> Optional[Dict]:
    ds = get_data_source(ds_key)
    if not ds:
        return None
    return next((f for f in ds['fields'] if f['key'] == field_key), None)
