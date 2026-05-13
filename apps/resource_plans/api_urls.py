from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .api_views import (
    ResourcePlanViewSet,
    ResourcePlanVersionConfigViewSet as VC,
    PlanPhaseViewSet as PV,
    AllocationGridViewSet as GV,
)

router = DefaultRouter()
router.register(r"resource-plans", ResourcePlanViewSet, basename="resource-plan")

# Nested version-config routes — relative to resource-plans/ prefix.
# Specific patterns must appear before more-general ones to avoid shadowing.
_vc_patterns = [
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/snapshots/(?P<snap_pk>\d+)/compare/$',
        GV.as_view({'get': 'snapshot_compare'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/snapshots/(?P<snap_pk>\d+)/allocations/$',
        GV.as_view({'get': 'snapshot_allocations'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/snapshots/(?P<snap_pk>\d+)/capacity/$',
        GV.as_view({'get': 'snapshot_capacity'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/snapshots/(?P<snap_pk>\d+)/$',
        GV.as_view({'get': 'snapshot_detail', 'delete': 'snapshot_delete'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/snapshots/$',
        GV.as_view({'get': 'snapshot_list', 'post': 'snapshot_create'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/utilisation/teams/$',
        GV.as_view({'get': 'utilisation_teams'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/utilisation/members/$',
        GV.as_view({'get': 'utilisation_members'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/utilisation/programmes/$',
        GV.as_view({'get': 'utilisation_programmes'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/cell/$',
        GV.as_view({'post': 'grid_cell_create'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/cell/(?P<alloc_pk>\d+)/$',
        GV.as_view({'post': 'grid_cell_update'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/conflicts/summary/$',
        GV.as_view({'get': 'conflict_summary'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/conflicts/(?P<conflict_pk>\d+)/resolve/$',
        GV.as_view({'post': 'conflict_resolve'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/conflicts/(?P<conflict_pk>\d+)/$',
        GV.as_view({'get': 'conflict_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/conflicts/$',
        GV.as_view({'get': 'conflict_list'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/manpower-requests/(?P<mp_pk>\d+)/hire/$',
        GV.as_view({'post': 'manpower_hire'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/manpower-requests/(?P<mp_pk>\d+)/rebalance/$',
        GV.as_view({'post': 'manpower_rebalance'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/manpower-requests/(?P<mp_pk>\d+)/dismiss/$',
        GV.as_view({'post': 'manpower_dismiss'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/manpower-requests/(?P<mp_pk>\d+)/$',
        GV.as_view({'get': 'manpower_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/manpower-requests/$',
        GV.as_view({'get': 'manpower_list'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/allocation-sets/(?P<set_pk>\d+)/activate/$',
        GV.as_view({'post': 'allocation_set_activate'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/allocation-sets/(?P<set_pk>\d+)/$',
        GV.as_view({'get': 'allocation_set_detail', 'patch': 'allocation_set_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/allocation-sets/$',
        GV.as_view({'get': 'allocation_sets'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/allocations/$',
        GV.as_view({'get': 'grid_allocations'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/allocated-capacity/$',
        GV.as_view({'get': 'grid_allocated_capacity'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/teams/$',
        GV.as_view({'get': 'grid_teams'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/capacity/$',
        GV.as_view({'get': 'grid_capacity'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/grid/absences/$',
        GV.as_view({'get': 'grid_absences'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-leaves/(?P<pl_pk>\d+)/$',
        GV.as_view({'patch': 'placeholder_leave_detail', 'delete': 'placeholder_leave_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-leaves/$',
        GV.as_view({'get': 'placeholder_leaves'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-engineers/(?P<ph_pk>\d+)/replace/$',
        GV.as_view({'post': 'placeholder_engineer_replace'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-engineers/(?P<ph_pk>\d+)/absences/(?P<absence_pk>\d+)/$',
        GV.as_view({'patch': 'placeholder_engineer_absence_update'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-engineers/(?P<ph_pk>\d+)/absences/$',
        GV.as_view({'get': 'placeholder_engineer_absence_list'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-engineers/(?P<ph_pk>\d+)/$',
        GV.as_view({'get': 'placeholder_engineer_detail', 'patch': 'placeholder_engineer_update'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/placeholder-engineers/$',
        GV.as_view({'get': 'placeholder_engineer_list'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/$',
        VC.as_view({'get': 'retrieve', 'patch': 'partial_update'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/unmapped/$',
        VC.as_view({'get': 'projects_unmapped'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/options/$',
        VC.as_view({'get': 'projects_options'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/$',
        VC.as_view({'get': 'projects', 'post': 'projects'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/resync/$',
        VC.as_view({'post': 'project_resync'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/reorder/$',
        VC.as_view({'patch': 'project_reorder'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/teams/options/$',
        VC.as_view({'get': 'teams_options'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/options/$',
        PV.as_view({'get': 'phases_options'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/segments/suggest/$',
        PV.as_view({'post': 'phase_segments_suggest'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/segments/reorder/$',
        PV.as_view({'post': 'phase_segments_reorder'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/segments/(?P<seg_pk>\d+)/$',
        PV.as_view({'patch': 'phase_segment_detail', 'delete': 'phase_segment_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/segments/$',
        PV.as_view({'get': 'phase_segments', 'post': 'phase_segments'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/dependencies/(?P<dep_pk>\d+)/$',
        PV.as_view({'patch': 'phase_dependency_detail', 'delete': 'phase_dependency_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/dependencies/$',
        PV.as_view({'get': 'phase_dependencies', 'post': 'phase_dependencies'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/pauses/(?P<pause_pk>\d+)/$',
        PV.as_view({'patch': 'phase_pause_detail', 'delete': 'phase_pause_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/pauses/$',
        PV.as_view({'get': 'phase_pauses', 'post': 'phase_pauses'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/$',
        PV.as_view({'get': 'phase_detail', 'patch': 'phase_detail', 'delete': 'phase_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/assignments/options/$',
        PV.as_view({'get': 'phase_assignments_options'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/assignments/(?P<assign_pk>\d+)/$',
        PV.as_view({'patch': 'phase_assignment_detail', 'delete': 'phase_assignment_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/phases/(?P<phase_pk>\d+)/assignments/$',
        PV.as_view({'get': 'phase_assignments', 'post': 'phase_assignments'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/teams/(?P<team_entry_pk>\d+)/phases/$',
        PV.as_view({'get': 'phases', 'post': 'phases'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/teams/(?P<team_entry_pk>\d+)/$',
        VC.as_view({'patch': 'team_detail', 'delete': 'team_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/teams/$',
        VC.as_view({'get': 'teams', 'post': 'teams'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/budget-releases/(?P<release_pk>\d+)/$',
        VC.as_view({'patch': 'budget_release_detail', 'delete': 'budget_release_detail'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/budget-releases/$',
        VC.as_view({'get': 'budget_releases', 'post': 'budget_releases'}),
    ),
    re_path(
        r'^(?P<plan_pk>\d+)/versions/(?P<pk>\d+)/projects/(?P<entry_pk>\d+)/$',
        VC.as_view({'get': 'project_detail', 'patch': 'project_detail', 'delete': 'project_detail'}),
    ),
]

urlpatterns = [
    path("", include(router.urls)),
    path("resource-plans/", include(_vc_patterns)),
]
