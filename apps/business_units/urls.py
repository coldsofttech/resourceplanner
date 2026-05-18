from django.urls import path
from .views import BusinessUnitListView

urlpatterns = [
    path('', BusinessUnitListView.as_view(), name='business_unit_list'),
]
