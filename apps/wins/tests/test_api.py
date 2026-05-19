"""
API tests for the Weekly Wins endpoints.

Scope:
  - GET /api/v1/wins/                      → list (auth required)
  - POST /api/v1/wins/                     → create
  - GET /api/v1/wins/<pk>/                 → retrieve
  - GET /api/v1/wins/next-week/            → next week suggestion
  - GET /api/v1/wins/<pk>/entries/         → list entries
  - POST /api/v1/wins/<pk>/entries/add/    → add entry
  - PATCH /api/v1/wins/entries/<pk>/       → update entry
  - DELETE /api/v1/wins/entries/<pk>/delete/ → delete entry
  - POST /api/v1/wins/<pk>/review-complete/ → review complete
  - GET /api/v1/wins/report-data/          → report data

Authentication: all wins endpoints require login; we use APIClient force_authenticate.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.delivery_teams.models import DeliveryTeam
from apps.wins.models import Win, WinEntry

User = get_user_model()

MONDAY = datetime.date(2025, 5, 12)


def make_win(week_number=1, start=MONDAY):
    return Win.objects.create(
        week_number=week_number,
        week_start_date=start,
        week_end_date=start + datetime.timedelta(days=6),
    )


class WinsAPIBase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api@test.com', email='api@test.com', password='x')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.team = DeliveryTeam.objects.create(name='Alpha')


class WinsListAPITest(WinsAPIBase):
    def test_unauthenticated_returns_403_or_redirect(self):
        client = APIClient()
        response = client.get('/api/v1/wins/')
        self.assertIn(response.status_code, [401, 403])

    def test_returns_paginated_results(self):
        make_win(1)
        make_win(2, MONDAY + datetime.timedelta(days=7))
        response = self.client.get('/api/v1/wins/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('pagination', response.data)
        self.assertEqual(response.data['pagination']['total_count'], 2)

    def test_empty_list(self):
        response = self.client.get('/api/v1/wins/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])


class CreateWinAPITest(WinsAPIBase):
    def test_create_valid(self):
        response = self.client.post('/api/v1/wins/', {'week_start_date': '2025-05-12'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['week_start_date'], '2025-05-12')
        self.assertEqual(response.data['week_end_date'], '2025-05-18')

    def test_create_non_monday_rejected(self):
        response = self.client.post('/api/v1/wins/', {'week_start_date': '2025-05-13'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_duplicate_rejected(self):
        make_win(1)
        response = self.client.post('/api/v1/wins/', {'week_start_date': '2025-05-12'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_date(self):
        response = self.client.post('/api/v1/wins/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_date_format(self):
        response = self.client.post('/api/v1/wins/', {'week_start_date': 'not-a-date'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RetrieveWinAPITest(WinsAPIBase):
    def test_retrieve_existing(self):
        win = make_win(1)
        response = self.client.get(f'/api/v1/wins/{win.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['week_number'], 1)
        self.assertIn('entries', response.data)

    def test_retrieve_not_found(self):
        response = self.client.get('/api/v1/wins/999999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NextWeekAPITest(WinsAPIBase):
    def test_returns_week_number_and_date(self):
        response = self.client.get('/api/v1/wins/next-week/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('week_number', response.data)
        self.assertIn('suggested_week_start', response.data)


class EntriesAPITest(WinsAPIBase):
    def setUp(self):
        super().setUp()
        self.win = make_win(1)

    def test_list_entries_empty(self):
        response = self.client.get(f'/api/v1/wins/{self.win.pk}/entries/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_add_entry_valid(self):
        response = self.client.post(
            f'/api/v1/wins/{self.win.pk}/entries/add/',
            {'team': self.team.pk, 'title': 'Great win', 'description': 'Context here.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Great win')
        self.assertEqual(response.data['description'], 'Context here.')

    def test_add_entry_missing_title(self):
        response = self.client.post(
            f'/api/v1/wins/{self.win.pk}/entries/add/',
            {'team': self.team.pk},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_entry_missing_team(self):
        response = self.client.post(
            f'/api/v1/wins/{self.win.pk}/entries/add/',
            {'title': 'Foo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_entry_win_not_found(self):
        response = self.client.post(
            '/api/v1/wins/999999/entries/add/',
            {'team': self.team.pk, 'title': 'Foo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_entries_with_filter(self):
        team2 = DeliveryTeam.objects.create(name='Beta')
        WinEntry.objects.create(win=self.win, team=self.team, title='Alpha win')
        WinEntry.objects.create(win=self.win, team=team2, title='Beta win')
        response = self.client.get(f'/api/v1/wins/{self.win.pk}/entries/?team_id={self.team.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Alpha win')


class UpdateEntryAPITest(WinsAPIBase):
    def setUp(self):
        super().setUp()
        self.win = make_win(1)
        self.entry = WinEntry.objects.create(win=self.win, team=self.team, title='Old')

    def test_update_title(self):
        response = self.client.patch(
            f'/api/v1/wins/entries/{self.entry.pk}/',
            {'title': 'New title', 'description': 'Updated desc'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'New title')

    def test_update_blank_title_rejected(self):
        response = self.client.patch(
            f'/api/v1/wins/entries/{self.entry.pk}/',
            {'title': ''},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_not_found(self):
        response = self.client.patch(
            '/api/v1/wins/entries/999999/',
            {'title': 'Foo'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DeleteEntryAPITest(WinsAPIBase):
    def setUp(self):
        super().setUp()
        self.win = make_win(1)
        self.entry = WinEntry.objects.create(win=self.win, team=self.team, title='To delete')

    def test_delete_returns_204(self):
        response = self.client.delete(f'/api/v1/wins/entries/{self.entry.pk}/delete/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WinEntry.objects.filter(pk=self.entry.pk).exists())

    def test_delete_nonexistent_returns_204(self):
        # Our implementation silently ignores missing entries
        response = self.client.delete('/api/v1/wins/entries/999999/delete/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class ReviewCompleteAPITest(WinsAPIBase):
    def setUp(self):
        super().setUp()
        self.win = make_win(1)
        WinEntry.objects.create(win=self.win, team=self.team, title='A win')

    @patch('apps.wins.services.WinService._send_review_email')
    def test_review_complete_success(self, mock_send):
        response = self.client.post(f'/api/v1/wins/{self.win.pk}/review-complete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'review_complete')

    @patch('apps.wins.services.WinService._send_review_email')
    def test_review_complete_idempotency_blocked(self, mock_send):
        self.client.post(f'/api/v1/wins/{self.win.pk}/review-complete/')
        response = self.client.post(f'/api/v1/wins/{self.win.pk}/review-complete/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_review_complete_not_found(self):
        response = self.client.post('/api/v1/wins/999999/review-complete/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ReportDataAPITest(WinsAPIBase):
    def setUp(self):
        super().setUp()
        self.win1 = make_win(1, datetime.date(2025, 5, 5))
        self.win2 = make_win(2, MONDAY)
        WinEntry.objects.create(win=self.win1, team=self.team, title='W1 entry')
        WinEntry.objects.create(win=self.win2, team=self.team, title='W2 entry')

    def test_by_week_ids(self):
        response = self.client.get(f'/api/v1/wins/report-data/?week_ids={self.win1.pk}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['rows']), 1)
        self.assertEqual(response.data['rows'][0]['title'], 'W1 entry')

    def test_by_date_range(self):
        response = self.client.get('/api/v1/wins/report-data/?date_from=2025-05-12&date_to=2025-05-18')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['rows']), 1)

    def test_all_wins_returned_when_no_filter(self):
        response = self.client.get('/api/v1/wins/report-data/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['rows']), 2)

    def test_invalid_week_ids_rejected(self):
        response = self.client.get('/api/v1/wins/report-data/?week_ids=abc')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_included(self):
        response = self.client.get('/api/v1/wins/report-data/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertEqual(response.data['summary'][0]['win_count'], 2)
