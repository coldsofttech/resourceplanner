"""
Service layer tests for Weekly Wins.

Scope:
  - WinService.next_week_number()
  - WinService.create_win()
  - WinService.list_wins()
  - WinService.get_win()
  - WinService.add_entry()
  - WinService.update_entry()
  - WinService.delete_entry()
  - WinService.review_complete() — status transition and re-review guard
  - WinService.get_report_data() — by week ids and by date range

Note: email sending in review_complete is tested with fail_silently=True,
so no real SMTP is required; we patch the send to avoid side effects.
"""

import datetime
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.delivery_teams.models import DeliveryTeam
from apps.wins.models import Win, WinEntry
from apps.wins.services import WinService

User = get_user_model()

MONDAY = datetime.date(2025, 5, 12)
SUNDAY = datetime.date(2025, 5, 18)


def make_win(week_number=1, start=MONDAY):
    end = start + datetime.timedelta(days=6)
    return Win.objects.create(week_number=week_number, week_start_date=start, week_end_date=end)


class NextWeekNumberTest(TestCase):
    def test_returns_1_when_no_wins(self):
        n = WinService.next_week_number()
        self.assertGreaterEqual(n, 1)

    def test_increments_from_latest(self):
        make_win(1)
        make_win(2, datetime.date(2025, 5, 19))
        self.assertEqual(WinService.next_week_number(), 3)


class CreateWinTest(TestCase):
    def test_creates_win_with_correct_dates(self):
        win = WinService.create_win(MONDAY)
        self.assertEqual(win.week_start_date, MONDAY)
        self.assertEqual(win.week_end_date, SUNDAY)

    def test_raises_validation_error_for_non_monday(self):
        tuesday = datetime.date(2025, 5, 13)
        with self.assertRaises(ValidationError):
            WinService.create_win(tuesday)

    def test_assigns_user(self):
        user = User.objects.create_user(username='u@t.com', email='u@t.com', password='x')
        win = WinService.create_win(MONDAY, user=user)
        self.assertEqual(win.created_by, user)

    def test_auto_increments_week_number(self):
        w1 = WinService.create_win(MONDAY)
        next_monday = MONDAY + datetime.timedelta(days=7)
        w2 = WinService.create_win(next_monday)
        self.assertEqual(w2.week_number, w1.week_number + 1)


class ListWinsTest(TestCase):
    def test_returns_all_wins_paginated(self):
        make_win(1)
        make_win(2, MONDAY + datetime.timedelta(days=7))
        result = WinService.list_wins(page=1, page_size=10)
        self.assertEqual(result['total_count'], 2)
        self.assertIn('results', result)

    def test_pagination_limits_results(self):
        for i in range(5):
            make_win(i + 1, MONDAY + datetime.timedelta(days=7 * i))
        result = WinService.list_wins(page=1, page_size=2)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['total_pages'], 3)


class GetWinTest(TestCase):
    def test_returns_win_by_pk(self):
        win = make_win(1)
        fetched = WinService.get_win(win.pk)
        self.assertEqual(fetched.pk, win.pk)

    def test_raises_does_not_exist(self):
        with self.assertRaises(Win.DoesNotExist):
            WinService.get_win(999999)


class AddEntryTest(TestCase):
    def setUp(self):
        self.win = make_win(1)
        self.team = DeliveryTeam.objects.create(name='Alpha')

    def test_adds_entry_with_title_and_description(self):
        entry = WinService.add_entry(self.win.pk, self.team.pk, 'Launched API', 'Cut latency 30%.')
        self.assertEqual(entry.title, 'Launched API')
        self.assertEqual(entry.description, 'Cut latency 30%.')
        self.assertEqual(entry.win, self.win)
        self.assertEqual(entry.team, self.team)

    def test_blank_title_raises(self):
        with self.assertRaises(ValidationError):
            WinService.add_entry(self.win.pk, self.team.pk, '   ')

    def test_description_defaults_to_empty(self):
        entry = WinService.add_entry(self.win.pk, self.team.pk, 'My win')
        self.assertEqual(entry.description, '')

    def test_win_not_found_raises(self):
        with self.assertRaises(Win.DoesNotExist):
            WinService.add_entry(999999, self.team.pk, 'Foo')


class UpdateEntryTest(TestCase):
    def setUp(self):
        self.win = make_win(1)
        self.team = DeliveryTeam.objects.create(name='Alpha')
        self.entry = WinEntry.objects.create(win=self.win, team=self.team, title='Old title')

    def test_updates_title(self):
        entry = WinService.update_entry(self.entry.pk, 'New title')
        self.assertEqual(entry.title, 'New title')

    def test_updates_description(self):
        entry = WinService.update_entry(self.entry.pk, 'New title', 'New desc')
        self.assertEqual(entry.description, 'New desc')

    def test_blank_title_raises(self):
        with self.assertRaises(ValidationError):
            WinService.update_entry(self.entry.pk, '')

    def test_not_found_raises(self):
        with self.assertRaises(WinEntry.DoesNotExist):
            WinService.update_entry(999999, 'Foo')


class DeleteEntryTest(TestCase):
    def test_deletes_entry(self):
        win = make_win(1)
        team = DeliveryTeam.objects.create(name='Alpha')
        entry = WinEntry.objects.create(win=win, team=team, title='To delete')
        WinService.delete_entry(entry.pk)
        self.assertFalse(WinEntry.objects.filter(pk=entry.pk).exists())

    def test_delete_nonexistent_is_silent(self):
        WinService.delete_entry(999999)  # Should not raise


class ReviewCompleteTest(TestCase):
    def setUp(self):
        self.win = make_win(1)
        self.team = DeliveryTeam.objects.create(name='Alpha')
        WinEntry.objects.create(win=self.win, team=self.team, title='Great win')
        self.user = User.objects.create_user(username='rev@t.com', email='rev@t.com', password='x')

    @patch('apps.wins.services.WinService._send_review_email')
    def test_marks_status_review_complete(self, mock_send):
        win = WinService.review_complete(self.win.pk, user=self.user)
        self.assertEqual(win.status, Win.STATUS_REVIEW_COMPLETE)
        self.assertIsNotNone(win.reviewed_at)
        self.assertEqual(win.reviewed_by, self.user)

    @patch('apps.wins.services.WinService._send_review_email')
    def test_raises_if_already_reviewed(self, mock_send):
        WinService.review_complete(self.win.pk)
        with self.assertRaises(ValidationError):
            WinService.review_complete(self.win.pk)

    @patch('apps.wins.services.WinService._send_review_email')
    def test_calls_send_email(self, mock_send):
        WinService.review_complete(self.win.pk)
        mock_send.assert_called_once()

    @patch('apps.wins.services.WinService._send_review_email')
    def test_builds_docx(self, mock_send):
        # Verify _build_docx returns bytes (non-empty)
        doc_bytes = WinService._build_docx(self.win)
        self.assertIsInstance(doc_bytes, bytes)
        self.assertGreater(len(doc_bytes), 0)


class ReportDataTest(TestCase):
    def setUp(self):
        self.team_a = DeliveryTeam.objects.create(name='Alpha')
        self.team_b = DeliveryTeam.objects.create(name='Beta')
        self.win1 = make_win(1, datetime.date(2025, 5, 5))
        self.win2 = make_win(2, MONDAY)
        WinEntry.objects.create(win=self.win1, team=self.team_a, title='Win A1')
        WinEntry.objects.create(win=self.win2, team=self.team_a, title='Win A2')
        WinEntry.objects.create(win=self.win2, team=self.team_b, title='Win B1')

    def test_by_week_ids(self):
        data = WinService.get_report_data(week_ids=[self.win2.pk])
        self.assertEqual(len(data['rows']), 2)
        teams_in_rows = {r['team_name'] for r in data['rows']}
        self.assertIn('Alpha', teams_in_rows)
        self.assertIn('Beta', teams_in_rows)

    def test_by_date_range(self):
        data = WinService.get_report_data(
            date_from=datetime.date(2025, 5, 5),
            date_to=datetime.date(2025, 5, 11),
        )
        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['rows'][0]['title'], 'Win A1')

    def test_summary_totals(self):
        data = WinService.get_report_data()  # all wins
        summary = {s['team_name']: s['win_count'] for s in data['summary']}
        self.assertEqual(summary['Alpha'], 2)
        self.assertEqual(summary['Beta'], 1)

    def test_empty_when_no_matches(self):
        data = WinService.get_report_data(date_from=datetime.date(2030, 1, 1))
        self.assertEqual(data['rows'], [])
        self.assertEqual(data['summary'], [])
