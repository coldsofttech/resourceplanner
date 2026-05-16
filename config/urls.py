"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.configurations.api_views import ConfigurationViewSet
from apps.contacts.api_views import ContactViewSet
from apps.delivery_teams.api_views import DeliveryTeamViewSet
from apps.employment_types.api_views import EmploymentTypeViewSet
from apps.financial_years.api_views import FinancialYearViewSet
from apps.member_leaves.api_views import MemberLeaveViewSet
from apps.office_locations.api_views import OfficeLocationViewSet
from apps.programmes.api_views import ProgrammeViewSet
from apps.project_sub_statuses.api_views import ProjectSubStatusViewSet
from apps.project_types.api_views import ProjectTypeViewSet
from apps.projects.api_views import ProjectViewSet, ProjectViewViewSet
from apps.public_holidays.api_views import PublicHolidayViewSet
from apps.skills.api_views import SkillViewSet
from apps.sprint_capacity.api_views import SprintCapacityViewSet
from apps.sprints.api_views import SprintViewSet
from apps.tags.api_views import TagViewSet
from apps.team_members.api_views import TeamMemberViewSet
from apps.team_roles.api_views import TeamRoleViewSet

router = DefaultRouter()
router.register(r"delivery-teams", DeliveryTeamViewSet, basename="delivery-team")
router.register(r"skills", SkillViewSet, basename="skill")
router.register(r"configurations", ConfigurationViewSet, basename="configuration")
router.register(r"locations", OfficeLocationViewSet, basename="location")
router.register(r"roles", TeamRoleViewSet, basename="role")
router.register(r"employment-types", EmploymentTypeViewSet, basename="employment-type")
router.register(r"team-members", TeamMemberViewSet, basename="team-member")
router.register(r"holidays", PublicHolidayViewSet, basename="holiday")
router.register(r"leaves", MemberLeaveViewSet, basename="leave")
router.register(r"fy", FinancialYearViewSet, basename="fy")
router.register(r"sprints", SprintViewSet, basename="sprint")
router.register(r"sprint-capacity", SprintCapacityViewSet, basename="sprint-capacity")
router.register(r"project-types", ProjectTypeViewSet, basename="project-type")
router.register(
    r"project-sub-statuses", ProjectSubStatusViewSet, basename="project-sub-status"
)
router.register(r"programmes", ProgrammeViewSet, basename="programme")
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"project-views", ProjectViewViewSet, basename="project-view")
router.register(r"tags", TagViewSet, basename="tag")

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth (classic login/register/logout/password-reset + SSO)
    path("", include("apps.users.urls")),
    # REST API – users
    path("api/v1/", include("apps.users.api_urls")),
    # REST API – permissions
    path("api/v1/", include("apps.permissions.api_urls")),
    # Permission categories admin UI
    path("permission-categories/", include("apps.permissions.urls")),
    # REST API – resource plans (includes nested version-config routes)
    path("api/v1/", include("apps.resource_plans.api_urls")),
    # REST API – all other apps
    path("api/v1/", include(router.urls)),
    # Manage
    path("delivery-teams/", include("apps.delivery_teams.urls")),
    path("team-members/", include("apps.team_members.urls")),
    path("leaves/", include("apps.member_leaves.urls")),
    path("fy/", include("apps.financial_years.urls")),
    path("sprints/", include("apps.sprints.urls")),
    # Projects
    path("programmes/", include("apps.programmes.urls")),
    path("projects/", include("apps.projects.urls")),
    path("resource-plans/", include("apps.resource_plans.urls")),
    path("contacts/", include("apps.contacts.urls")),
    # Settings
    path("holidays/", include("apps.public_holidays.urls")),
    path("skills/", include("apps.skills.urls")),
    path("locations/", include("apps.office_locations.urls")),
    path("roles/", include("apps.team_roles.urls")),
    path("employment-types/", include("apps.employment_types.urls")),
    path("project-types/", include("apps.project_types.urls")),
    path("project-sub-statuses/", include("apps.project_sub_statuses.urls")),
    path("configurations/", include("apps.configurations.urls")),
    # Generic Modules
    path("import/", include("apps.import.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
