from django.urls import path

from .api_views import ContactViewSet
from .views import ContactListView

app_name = "contacts"

urlpatterns = [
    path("", ContactListView.as_view(), name="list"),
    path(
        "import/sample/",
        ContactViewSet.as_view({"get": "import_sample"}),
        name="import_sample",
    ),
]
