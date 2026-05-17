from django.urls import path

from .views import (
    FinanceTypesPageView,
    ProjectActualsPageView,
    RechargesPageView,
    RechargeSprintPageView,
    RechargeEmailReviewPageView,
)

app_name = 'sprint_forecast'

urlpatterns = [
    path('recharges/', RechargesPageView.as_view(), name='recharges'),
    path('recharges/<int:sprint_id>/', RechargeSprintPageView.as_view(), name='recharge-sprint'),
    path('recharges/<int:sprint_id>/forecast/', RechargeEmailReviewPageView.as_view(), kwargs={'tab_type': 'FORECAST'}, name='recharge-review-forecast'),
    path('recharges/<int:sprint_id>/actuals/', RechargeEmailReviewPageView.as_view(), kwargs={'tab_type': 'ACTUAL'}, name='recharge-review-actuals'),
    path('finance-types/', FinanceTypesPageView.as_view(), name='finance-types'),
    path('project-actuals/', ProjectActualsPageView.as_view(), name='project-actuals'),
]
