"""
Model tests for the Wins app.

Scope:
  - Win: week_end_date auto-computation, clean() validation (must be Monday)
  - WinEntry: __str__, title/description fields, ordering
  - TeamProductOwner: unique_together constraint
  - MonthlyWin: status choices, string representation
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.delivery_teams.models import DeliveryTeam
from apps.wins.models import (
    CATEGORY_DELIVERY, CATEGORY_OPERATIONAL,
    MonthlyWin, TeamProductOwner, Win, WinEntry,
)

User = get_user_model()


class WinModelTest(TestCase):
    """Tests for the Win model."""

    def _monday(self):
        return datetime.date(2025, 5, 12)  # A known Monday

    def test_week_end_date_auto_computed(self):
        win = Win(week_number=1, week_start_date=self._monday())
        win.save()
        self.assertEqual(win.week_end_date, datetime.date(2025, 5, 18))

    def test_week_end_date_not_overwritten_if_set(self):
        custom_end = datetime.date(2025, 5, 15)
        win = Win(
            week_number=1,
            week_start_date=self._monday(),
            week_end_date=custom_end,
        )
        win.save()
        self.assertEqual(win.week_end_date, custom_end)

    def test_clean_raises_if_not_monday(self):
        tuesday = datetime.date(2025, 5, 13)
        win = Win(week_number=1, week_start_date=tuesday)
        with self.assertRaises(ValidationError):
            win.clean()

    def test_clean_passes_for_monday(self):
        win = Win(week_number=1, week_start_date=self._monday())
        win.clean()  # Should not raise

    def test_str_representation(self):
        win = Win(week_number=5, week_start_date=self._monday(), week_end_date=datetime.date(2025, 5, 18))
        self.assertIn('5', str(win))
        self.assertIn('2025-05-12', str(win))

    def test_default_status_is_open(self):
        win = Win.objects.create(
            week_number=1, week_start_date=self._monday(), week_end_date=datetime.date(2025, 5, 18)
        )
        self.assertEqual(win.status, Win.STATUS_OPEN)

    def test_ordering_newest_first(self):
        Win.objects.create(week_number=1, week_start_date=datetime.date(2025, 5, 5), week_end_date=datetime.date(2025, 5, 11))
        Win.objects.create(week_number=2, week_start_date=self._monday(), week_end_date=datetime.date(2025, 5, 18))
        first = Win.objects.first()
        self.assertEqual(first.week_number, 2)


class WinEntryModelTest(TestCase):
    """Tests for the WinEntry model."""

    def setUp(self):
        self.team = DeliveryTeam.objects.create(name='Alpha')
        self.win = Win.objects.create(
            week_number=1,
            week_start_date=datetime.date(2025, 5, 12),
            week_end_date=datetime.date(2025, 5, 18),
        )

    def test_creates_with_title_and_description(self):
        entry = WinEntry.objects.create(
            win=self.win,
            team=self.team,
            title='Launched new dashboard',
            description='Saved 2h/week per user.',
        )
        self.assertEqual(entry.title, 'Launched new dashboard')
        self.assertEqual(entry.description, 'Saved 2h/week per user.')

    def test_description_is_optional(self):
        entry = WinEntry.objects.create(win=self.win, team=self.team, title='Quick win')
        self.assertEqual(entry.description, '')

    def test_str_includes_week_and_team(self):
        entry = WinEntry(win=self.win, team=self.team, title='Foo')
        s = str(entry)
        self.assertIn('1', s)
        self.assertIn('Alpha', s)

    def test_ordering_by_team_then_created(self):
        beta = DeliveryTeam.objects.create(name='Beta')
        WinEntry.objects.create(win=self.win, team=beta, title='B entry')
        WinEntry.objects.create(win=self.win, team=self.team, title='A entry')
        entries = list(WinEntry.objects.all())
        self.assertEqual(entries[0].team.name, 'Alpha')


class TeamProductOwnerModelTest(TestCase):
    """Tests for the TeamProductOwner model."""

    def setUp(self):
        self.team = DeliveryTeam.objects.create(name='Alpha')
        self.user = User.objects.create_user(username='po@test.com', email='po@test.com', password='x')

    def test_create(self):
        tpo = TeamProductOwner.objects.create(team=self.team, user=self.user)
        self.assertTrue(tpo.is_active)

    def test_unique_together_enforced(self):
        TeamProductOwner.objects.create(team=self.team, user=self.user)
        with self.assertRaises(Exception):
            TeamProductOwner.objects.create(team=self.team, user=self.user)

    def test_str(self):
        tpo = TeamProductOwner(team=self.team, user=self.user)
        s = str(tpo)
        self.assertIn('Alpha', s)
        self.assertIn('po@test.com', s)


class MonthlyWinModelTest(TestCase):
    """Tests for the MonthlyWin model."""

    def test_default_status_draft(self):
        user = User.objects.create_user(username='u@test.com', email='u@test.com', password='x')
        mw = MonthlyWin.objects.create(name='May 2025', created_by=user)
        self.assertEqual(mw.status, MonthlyWin.STATUS_DRAFT)

    def test_str(self):
        mw = MonthlyWin(name='April 2025')
        self.assertEqual(str(mw), 'April 2025')
