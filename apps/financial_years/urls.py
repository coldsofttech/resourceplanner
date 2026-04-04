from django.urls import path

from .api_views import FinancialYearViewSet
from .views import (
    FinancialYearListView,
    FinancialYearCreateView,
    FinancialYearDetailView,
    FinancialYearUpdateView,
)

app_name = 'financial-years'

urlpatterns = [
    path('', FinancialYearListView.as_view(), name='list'),
    path('new/', FinancialYearCreateView.as_view(), name='create'),
    path('import/sample/', FinancialYearViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    path('<int:pk>/', FinancialYearDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', FinancialYearUpdateView.as_view(), name='edit'),
]
