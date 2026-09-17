"""Tests for the Diary / EMA scheduling and compliance helpers (commit 1).

Pure-function tests for ``checktick_app/surveys/diary.py``. These use
``SimpleNamespace`` to create synthetic menu-like and entry-like objects
— no Django models or migrations are needed. The runtime hook (commit 4)
and organise UI (commit 5) build on top of these.

Covers:
- ``anchor_time`` — enrolment vs survey_open anchor.
- ``window_for_order`` — fixed_interval, burst, event_triggered.
- ``current_window`` — open window, between windows, grace period, burst
  off-period, event_triggered (always None).
- ``next_window`` — next upcoming window after now.
- ``expected_entry_count`` — compliance denominator.
- ``compliance_for_progress`` — submitted / missed / compliance_pct.
"""

from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone
import pytest

from checktick_app.surveys.diary import (
    DEFAULT_GRACE_MINUTES,
    anchor_time,
    compliance_for_progress,
    current_window,
    expected_entry_count,
    next_window,
    window_for_order,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _fixed_interval_menu(
    *,
    interval_hours=6,
    anchor="enrolment",
    grace_minutes=DEFAULT_GRACE_MINUTES,
):
    return SimpleNamespace(
        schedule_type="fixed_interval",
        interval_hours=interval_hours,
        burst_on_days=None,
        burst_off_days=None,
        anchor=anchor,
        grace_minutes=grace_minutes,
    )


def _burst_menu(
    *,
    on_days=7,
    off_days=7,
    interval_hours=None,
    anchor="enrolment",
    grace_minutes=DEFAULT_GRACE_MINUTES,
):
    return SimpleNamespace(
        schedule_type="burst",
        interval_hours=interval_hours,
        burst_on_days=on_days,
        burst_off_days=off_days,
        anchor=anchor,
        grace_minutes=grace_minutes,
    )


def _event_menu(*, anchor="enrolment", grace_minutes=DEFAULT_GRACE_MINUTES):
    return SimpleNamespace(
        schedule_type="event_triggered",
        interval_hours=None,
        burst_on_days=None,
        burst_off_days=None,
        anchor=anchor,
        grace_minutes=grace_minutes,
    )


def _entry(order, *, submitted_at=None, is_missed=False):
    return SimpleNamespace(
        order=order,
        submitted_at=submitted_at,
        is_missed=is_missed,
    )


@pytest.fixture
def now():
    return timezone.now()


# ---------------------------------------------------------------------------
# anchor_time
# ---------------------------------------------------------------------------


def test_anchor_enrolment_uses_enrolment(now):
    menu = _fixed_interval_menu()
    survey_start = now - timedelta(days=10)
    enrolment = now - timedelta(days=2)
    assert (
        anchor_time(menu, enrolment=enrolment, survey_start=survey_start) == enrolment
    )


def test_anchor_enrolment_falls_back_to_survey_start(now):
    menu = _fixed_interval_menu()
    survey_start = now - timedelta(days=10)
    assert anchor_time(menu, enrolment=None, survey_start=survey_start) == survey_start


def test_anchor_survey_open_uses_survey_start(now):
    menu = _fixed_interval_menu(anchor="survey_open")
    enrolment = now - timedelta(days=2)
    survey_start = now - timedelta(days=10)
    assert (
        anchor_time(menu, enrolment=enrolment, survey_start=survey_start)
        == survey_start
    )


def test_anchor_survey_open_none_survey_start_returns_none(now):
    menu = _fixed_interval_menu(anchor="survey_open")
    assert anchor_time(menu, enrolment=now, survey_start=None) is None


# ---------------------------------------------------------------------------
# window_for_order — fixed_interval
# ---------------------------------------------------------------------------


def test_window_for_order_fixed_interval_first(now):
    menu = _fixed_interval_menu(interval_hours=6)
    start, end = window_for_order(menu, 0, anchor=now)
    assert start == now
    assert end == now + timedelta(hours=6)


def test_window_for_order_fixed_interval_third(now):
    menu = _fixed_interval_menu(interval_hours=6)
    start, end = window_for_order(menu, 2, anchor=now)
    assert start == now + timedelta(hours=12)
    assert end == now + timedelta(hours=18)


# ---------------------------------------------------------------------------
# window_for_order — burst
# ---------------------------------------------------------------------------


def test_window_for_order_burst_first_window(now):
    menu = _burst_menu(on_days=7, off_days=7)
    start, end = window_for_order(menu, 0, anchor=now)
    assert start == now
    assert end == now + timedelta(hours=24)


def test_window_for_order_burst_crosses_into_off_period(now):
    """Window order 7 (8th on-day) should be in the second cycle, day 0."""
    menu = _burst_menu(on_days=7, off_days=7)
    # order 7 = cycle 1, day 0 → day_offset = 14 (7 on + 7 off)
    start, end = window_for_order(menu, 7, anchor=now)
    assert start == now + timedelta(days=14)
    assert end == now + timedelta(days=14, hours=24)


def test_window_for_order_burst_uses_interval_hours_if_set(now):
    menu = _burst_menu(on_days=3, off_days=4, interval_hours=12)
    start, end = window_for_order(menu, 0, anchor=now)
    assert start == now
    assert end == now + timedelta(hours=12)


# ---------------------------------------------------------------------------
# window_for_order — event_triggered
# ---------------------------------------------------------------------------


def test_window_for_order_event_triggered_returns_none(now):
    menu = _event_menu()
    assert window_for_order(menu, 0, anchor=now) is None


# ---------------------------------------------------------------------------
# window_for_order — invalid config
# ---------------------------------------------------------------------------


def test_window_for_order_fixed_interval_no_interval_returns_none(now):
    menu = _fixed_interval_menu(interval_hours=None)
    assert window_for_order(menu, 0, anchor=now) is None


def test_window_for_order_burst_no_on_days_returns_none(now):
    menu = _burst_menu(on_days=0, off_days=7)
    assert window_for_order(menu, 0, anchor=now) is None


def test_window_for_order_none_anchor_returns_none():
    menu = _fixed_interval_menu()
    assert window_for_order(menu, 0, anchor=None) is None


# ---------------------------------------------------------------------------
# current_window — fixed_interval
# ---------------------------------------------------------------------------


def test_current_window_fixed_interval_at_anchor(now):
    menu = _fixed_interval_menu(interval_hours=6)
    result = current_window(menu, anchor=now, now=now)
    assert result is not None
    order, start, end = result
    assert order == 0
    assert start == now
    assert end == now + timedelta(hours=6)


def test_current_window_fixed_interval_mid_window(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=3)
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 0
    assert start == anchor
    assert end == anchor + timedelta(hours=6)


def test_current_window_fixed_interval_second_window(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=8)
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 1
    assert start == anchor + timedelta(hours=6)
    assert end == anchor + timedelta(hours=12)


def test_current_window_fixed_interval_in_grace(now):
    """Now is past window end but within grace → still open."""
    menu = _fixed_interval_menu(interval_hours=6, grace_minutes=30)
    anchor = now - timedelta(hours=6, minutes=10)
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 0


def test_current_window_fixed_interval_past_grace(now):
    """Now is past window end + grace → next window is open (back-to-back)."""
    menu = _fixed_interval_menu(interval_hours=6, grace_minutes=30)
    anchor = now - timedelta(hours=6, minutes=45)
    # Window 0 ended 6h ago, +30min grace = 6h30m ago. We're 15 min past grace.
    # Window 1 started 6h ago, ends now. So window 1 should be open.
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 1


def test_current_window_fixed_interval_before_anchor(now):
    """Now is before the anchor → no window open."""
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now + timedelta(hours=1)
    assert current_window(menu, anchor=anchor, now=now) is None


def test_current_window_none_anchor_returns_none(now):
    menu = _fixed_interval_menu()
    assert current_window(menu, anchor=None, now=now) is None


# ---------------------------------------------------------------------------
# current_window — burst
# ---------------------------------------------------------------------------


def test_current_window_burst_on_day(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 3 of first on-period.
    anchor = now - timedelta(days=3, hours=1)
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 3  # 4th on-day (0-indexed)


def test_current_window_burst_off_period(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 10 — in the off-period (days 7-13 are off).
    anchor = now - timedelta(days=10)
    assert current_window(menu, anchor=anchor, now=now) is None


def test_current_window_burst_second_cycle(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 15 — second cycle, day 1 (on-day).
    anchor = now - timedelta(days=15, hours=1)
    result = current_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    # Second cycle: cycle_index=1, day_in_cycle=1 → order = 1*7 + 1 = 8
    assert order == 8


def test_current_window_burst_past_window_grace(now):
    """On-day but past the daily window + grace → None (next window tomorrow)."""
    menu = _burst_menu(on_days=7, off_days=7, interval_hours=6, grace_minutes=30)
    # Anchor at midnight; now is 7 hours later (window was 0-6h, grace 30min).
    anchor = now - timedelta(hours=7, minutes=10)
    # But we need the day to be an on-day. Set anchor to a time such that
    # the elapsed days put us in an on-period.
    # Actually, let's just set anchor = now - 1 day - 7h10m so we're on day 1.
    anchor = now - timedelta(days=1, hours=7, minutes=10)
    result = current_window(menu, anchor=anchor, now=now)
    # Window for day 1 opened at anchor + 1 day, lasted 6h, grace 30min.
    # now is 7h10m after that → past grace. No window open.
    assert result is None


# ---------------------------------------------------------------------------
# current_window — event_triggered
# ---------------------------------------------------------------------------


def test_current_window_event_triggered_always_none(now):
    menu = _event_menu()
    assert current_window(menu, anchor=now, now=now) is None


# ---------------------------------------------------------------------------
# next_window
# ---------------------------------------------------------------------------


def test_next_window_fixed_interval_before_anchor(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now + timedelta(hours=1)
    result = next_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 0
    assert start == anchor


def test_next_window_fixed_interval_after_current(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=3)
    # Current window is 0 (3h into a 6h window). Next is window 1.
    result = next_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 1
    assert start == anchor + timedelta(hours=6)


def test_next_window_burst_in_off_period(now):
    """In an off-period, next_window should find the next on-day."""
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 10 — off-period. Next on-day is day 14 (start of cycle 2).
    anchor = now - timedelta(days=10)
    result = next_window(menu, anchor=anchor, now=now)
    assert result is not None
    order, start, end = result
    assert order == 7  # First on-day of cycle 2
    assert start == anchor + timedelta(days=14)


def test_next_window_event_triggered_returns_none(now):
    menu = _event_menu()
    assert next_window(menu, anchor=now, now=now) is None


def test_next_window_none_anchor_returns_none(now):
    menu = _fixed_interval_menu()
    assert next_window(menu, anchor=None, now=now) is None


# ---------------------------------------------------------------------------
# expected_entry_count
# ---------------------------------------------------------------------------


def test_expected_entry_count_fixed_interval(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=20)
    # 20h / 6h = 3 full windows + current = 4 expected.
    assert expected_entry_count(menu, anchor=anchor, now=now) == 4


def test_expected_entry_count_fixed_interval_at_anchor(now):
    menu = _fixed_interval_menu(interval_hours=6)
    assert expected_entry_count(menu, anchor=now, now=now) == 1


def test_expected_entry_count_before_anchor(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now + timedelta(hours=1)
    assert expected_entry_count(menu, anchor=anchor, now=now) == 0


def test_expected_entry_count_burst_mid_on_period(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 3 of first on-period → 4 expected (days 0,1,2,3).
    anchor = now - timedelta(days=3)
    assert expected_entry_count(menu, anchor=anchor, now=now) == 4


def test_expected_entry_count_burst_in_off_period(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 10 — off-period. 7 on-days completed.
    anchor = now - timedelta(days=10)
    assert expected_entry_count(menu, anchor=anchor, now=now) == 7


def test_expected_entry_count_burst_second_cycle(now):
    menu = _burst_menu(on_days=7, off_days=7)
    # Day 15 — second cycle, day 1. 7 (cycle 1) + 2 (days 0,1 of cycle 2) = 9.
    anchor = now - timedelta(days=15)
    assert expected_entry_count(menu, anchor=anchor, now=now) == 9


def test_expected_entry_count_event_triggered(now):
    menu = _event_menu()
    assert expected_entry_count(menu, anchor=now, now=now) == 0


def test_expected_entry_count_none_anchor(now):
    menu = _fixed_interval_menu()
    assert expected_entry_count(menu, anchor=None, now=now) == 0


# ---------------------------------------------------------------------------
# compliance_for_progress
# ---------------------------------------------------------------------------


def test_compliance_all_submitted(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=20)
    # 4 expected. 4 submitted.
    entries = [
        _entry(0, submitted_at=now - timedelta(hours=18)),
        _entry(1, submitted_at=now - timedelta(hours=12)),
        _entry(2, submitted_at=now - timedelta(hours=6)),
        _entry(3, submitted_at=now),
    ]
    result = compliance_for_progress(menu, entries, anchor=anchor, now=now)
    assert result["expected"] == 4
    assert result["submitted"] == 4
    assert result["missed"] == 0
    assert result["compliance_pct"] == 100.0
    assert result["missed_orders"] == []


def test_compliance_partial(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=20)
    # 4 expected. 2 submitted, 1 missed, 1 pending.
    entries = [
        _entry(0, submitted_at=now - timedelta(hours=18)),
        _entry(1, submitted_at=None, is_missed=True),
        _entry(2, submitted_at=now - timedelta(hours=6)),
        _entry(3, submitted_at=None, is_missed=False),
    ]
    result = compliance_for_progress(menu, entries, anchor=anchor, now=now)
    assert result["expected"] == 4
    assert result["submitted"] == 2
    assert result["missed"] == 1
    assert result["compliance_pct"] == 50.0
    assert result["missed_orders"] == [1]


def test_compliance_none_submitted(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=20)
    entries = [
        _entry(0, submitted_at=None, is_missed=True),
        _entry(1, submitted_at=None, is_missed=True),
        _entry(2, submitted_at=None, is_missed=True),
        _entry(3, submitted_at=None, is_missed=False),
    ]
    result = compliance_for_progress(menu, entries, anchor=anchor, now=now)
    assert result["expected"] == 4
    assert result["submitted"] == 0
    assert result["missed"] == 3
    assert result["compliance_pct"] == 0.0
    assert result["missed_orders"] == [0, 1, 2]


def test_compliance_event_triggered(now):
    """Event-triggered: expected=0, compliance_pct=0."""
    menu = _event_menu()
    entries = [
        _entry(0, submitted_at=now - timedelta(hours=1)),
        _entry(1, submitted_at=now - timedelta(minutes=30)),
    ]
    result = compliance_for_progress(menu, entries, anchor=now, now=now)
    assert result["expected"] == 0
    assert result["submitted"] == 2
    assert result["missed"] == 0
    assert result["compliance_pct"] == 0.0


def test_compliance_empty_entries(now):
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=20)
    result = compliance_for_progress(menu, [], anchor=anchor, now=now)
    assert result["expected"] == 4
    assert result["submitted"] == 0
    assert result["missed"] == 0
    assert result["compliance_pct"] == 0.0
    assert result["missed_orders"] == []


def test_compliance_below_threshold(now):
    """Compliance below 80% threshold — the dashboard highlights this."""
    menu = _fixed_interval_menu(interval_hours=6)
    anchor = now - timedelta(hours=50)
    # 50h / 6h = 8 full + current = 9 expected.
    # Only 2 submitted → ~22% compliance.
    entries = [
        _entry(0, submitted_at=now - timedelta(hours=48)),
        _entry(1, submitted_at=now - timedelta(hours=42)),
    ]
    result = compliance_for_progress(menu, entries, anchor=anchor, now=now)
    assert result["expected"] == 9
    assert result["submitted"] == 2
    assert result["compliance_pct"] == pytest.approx(22.22, abs=0.1)
