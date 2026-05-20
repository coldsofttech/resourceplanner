from django.urls import path
from .views import BoardCardsConfigView

app_name = 'board_cards'

urlpatterns = [
    path('', BoardCardsConfigView.as_view(), name='board-cards'),
]
