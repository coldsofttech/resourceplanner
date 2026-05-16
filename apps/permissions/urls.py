from django.urls import path
from .views import category_list_view

urlpatterns = [
    path('', category_list_view, name='permission-category-list'),
]
