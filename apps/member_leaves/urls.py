from django.urls import path

from .api_views import MemberLeaveViewSet
from .views import MemberLeaveListView, MemberLeaveCreateView, MemberLeaveDetailView, MemberLeaveUpdateView

app_name = 'leaves'

urlpatterns = [
    path('', MemberLeaveListView.as_view(), name='list'),
    path('new/', MemberLeaveCreateView.as_view(), name='create'),
    path('import/sample/', MemberLeaveViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    path('<int:pk>/', MemberLeaveDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', MemberLeaveUpdateView.as_view(), name='edit'),
]
