from django.urls import path
from . import views

app_name = "resource-plans"

urlpatterns = [
    path("", views.ResourcePlanListView.as_view(), name="plan_list"),
    path("<int:pk>/", views.ResourcePlanDetailView.as_view(), name="plan_detail"),
    path("<int:plan_pk>/versions/<int:version_pk>/", views.VersionConfigureView.as_view(), name="version_configure"),
    path("<int:plan_pk>/versions/<int:version_pk>/grid/", views.AllocationGridView.as_view(), name="allocation_grid"),
    path("<int:plan_pk>/versions/<int:version_pk>/placeholder-leaves/", views.PlaceholderLeavesView.as_view(), name="placeholder_leaves"),
    path("<int:plan_pk>/versions/<int:version_pk>/conflicts/", views.ConflictsView.as_view(), name="conflicts"),
    path("<int:plan_pk>/versions/<int:version_pk>/utilisation/", views.UtilisationView.as_view(), name="utilisation"),
    path("<int:plan_pk>/versions/<int:version_pk>/snapshots/", views.SnapshotsView.as_view(), name="snapshots"),
    path("<int:plan_pk>/versions/<int:version_pk>/audit/", views.AuditLogView.as_view(), name="audit_log"),
]
