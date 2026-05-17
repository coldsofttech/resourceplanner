from django.urls import path

from .views import FinanceTypesPageView, ProjectActualsPageView, RechargesPageView

app_name = 'sprint_forecast'

urlpatterns = [
    path('recharges/', RechargesPageView.as_view(), name='recharges'),
    path('finance-types/', FinanceTypesPageView.as_view(), name='finance-types'),
    path('project-actuals/', ProjectActualsPageView.as_view(), name='project-actuals'),
]
