from django.urls import path

from .api_views import PublicHolidayViewSet
from .views import PublicHolidayListView, PublicHolidayCreateView, PublicHolidayDetailView, PublicHolidayUpdateView

app_name = 'holidays'

urlpatterns = [
    path('', PublicHolidayListView.as_view(), name='list'),
    path('new/', PublicHolidayCreateView.as_view(), name='create'),
    path('import/sample/', PublicHolidayViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    path('<int:pk>/', PublicHolidayDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', PublicHolidayUpdateView.as_view(), name='edit'),
]
