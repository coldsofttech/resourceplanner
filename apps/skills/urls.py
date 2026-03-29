from django.urls import path

from .api_views import SkillViewSet
from .views import SkillListView, SkillCreateView, SkillDetailView, SkillUpdateView, SkillDeleteView, SkillImportView

app_name = 'skills'

urlpatterns = [
    path('', SkillListView.as_view(), name='list'),  # list all skills
    path('new/', SkillCreateView.as_view(), name='create'),  # create a new skill
    path('import/', SkillImportView.as_view(), name='import'),  # bulk import skills
    path('import/sample/', SkillViewSet.as_view({'get': 'import_sample'}), name='import_sample'),
    # download sample import template
    path('<int:pk>/', SkillDetailView.as_view(), name='detail'),  # view the specified skill
    path('<int:pk>/edit/', SkillUpdateView.as_view(), name='edit'),  # update the specified skill
    path('<int:pk>/delete/', SkillDeleteView.as_view(), name='delete'),  # delete the specified skill
]
