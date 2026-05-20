from django.urls import path

from .api_views import (
    OrgChartNodeListCreateView,
    OrgChartNodeDetailView,
    OrgChartImportView,
    OrgChartTeamsView,
    OrgChartMembersView,
)

urlpatterns = [
    path('orgchart/nodes/',          OrgChartNodeListCreateView.as_view(), name='orgchart-nodes'),
    path('orgchart/nodes/<int:pk>/', OrgChartNodeDetailView.as_view(),     name='orgchart-node-detail'),
    path('orgchart/import/',         OrgChartImportView.as_view(),         name='orgchart-import'),
    path('orgchart/teams/',          OrgChartTeamsView.as_view(),          name='orgchart-teams'),
    path('orgchart/members/',        OrgChartMembersView.as_view(),        name='orgchart-members'),
]
