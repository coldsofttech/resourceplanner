from django.urls import path

from .views import RechargeContactsListView

app_name = 'recharge_contacts'

urlpatterns = [
    path('', RechargeContactsListView.as_view(), name='recharge_contacts'),
]
