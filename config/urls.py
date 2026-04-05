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
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.configurations.api_views import ConfigurationViewSet
from apps.delivery_teams.api_views import DeliveryTeamViewSet
from apps.employment_types.api_views import EmploymentTypeViewSet
from apps.financial_years.api_views import FinancialYearViewSet
from apps.member_leaves.api_views import MemberLeaveViewSet
from apps.office_locations.api_views import OfficeLocationViewSet
from apps.public_holidays.api_views import PublicHolidayViewSet
from apps.skills.api_views import SkillViewSet
from apps.sprint_capacity.api_views import SprintCapacityViewSet
from apps.sprints.api_views import SprintViewSet
from apps.team_members.api_views import TeamMemberViewSet
from apps.team_roles.api_views import TeamRoleViewSet

router = DefaultRouter()
router.register(r'delivery-teams', DeliveryTeamViewSet, basename='delivery-team')
router.register(r'skills', SkillViewSet, basename='skill')
router.register(r'configurations', ConfigurationViewSet, basename='configuration')
router.register(r'locations', OfficeLocationViewSet, basename='location')
router.register(r'roles', TeamRoleViewSet, basename='role')
router.register(r'employment-types', EmploymentTypeViewSet, basename='employment-type')
router.register(r'team-members', TeamMemberViewSet, basename='team-member')
router.register(r'holidays', PublicHolidayViewSet, basename='holiday')
router.register(r'leaves', MemberLeaveViewSet, basename='leave')
router.register(r'fy', FinancialYearViewSet, basename='fy')
router.register(r'sprints', SprintViewSet, basename='sprint')
router.register(r'sprint-capacity', SprintCapacityViewSet, basename='sprint-capacity')

urlpatterns = [
    path('admin/', admin.site.urls),

    # REST API
    path('api/v1/', include(router.urls)),

    # Manage
    path('delivery-teams/', include('apps.delivery_teams.urls')),
    path('team-members/', include('apps.team_members.urls')),
    path('leaves/', include('apps.member_leaves.urls')),
    path('fy/', include('apps.financial_years.urls')),
    path('sprints/', include('apps.sprints.urls')),

    # Settings
    path('holidays/', include('apps.public_holidays.urls')),
    path('skills/', include('apps.skills.urls')),
    path('locations/', include('apps.office_locations.urls')),
    path('roles/', include('apps.team_roles.urls')),
    path('employment-types/', include('apps.employment_types.urls')),
    path('configurations/', include('apps.configurations.urls')),

    # Generic Modules
    path('import/', include('apps.import.urls')),

    path('', include('apps.delivery_teams.urls')),
]
