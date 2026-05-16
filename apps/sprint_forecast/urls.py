from django.urls import path

from .views import FinanceTypesPageView, RechargesPageView

app_name = 'sprint_forecast'

urlpatterns = [
    path('recharges/', RechargesPageView.as_view(), name='recharges'),
    path('finance-types/', FinanceTypesPageView.as_view(), name='finance-types'),
]
