from django.urls import path

from . import views

urlpatterns = [
    path('', views.wins_list, name='wins-list'),
    path('<int:pk>/', views.win_detail, name='win-detail'),
    path('report/', views.wins_report, name='wins-report'),
    path('monthly/', views.monthly_wins_list, name='monthly-wins-list'),
    path('monthly/product-owners/', views.product_owners, name='product-owners'),
    path('monthly/<int:pk>/', views.monthly_win_detail, name='monthly-win-detail'),
    path('monthly/<int:pk>/report/', views.monthly_win_report, name='monthly-win-report'),
    path('survey/<uuid:token>/', views.monthly_win_survey, name='monthly-win-survey'),
]
