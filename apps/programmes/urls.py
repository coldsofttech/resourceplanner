from django.urls import path

from .api_views import ProgrammeViewSet
from .views import ProgrammeListView

app_name = "programmes"

urlpatterns = [
    path("", ProgrammeListView.as_view(), name="list"),
    path(
        "import/sample/",
        ProgrammeViewSet.as_view({"get": "import_sample"}),
        name="import_sample",
    ),
]
