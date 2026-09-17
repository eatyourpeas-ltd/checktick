"""Diary / EMA layout scheduling and compliance helpers.

Pure, testable functions used by the take view to compute which diary
window is currently open for a participant, and to calculate compliance
(missed entries) across the schedule. Kept separate from the runtime
pipeline so the diary scheduler sits next to ``staged.py`` and
``delphi.py`` without touching the take view (see
``docs/diary-ema-implementation-plan.md`` §4).

A diary window is open at time ``now`` when::

    anchor + window_start <= now < anchor + window_end + grace

where ``grace`` is a short extension (default 30 min) that prevents
edge-case missed entries when the participant is a few minutes late.

Schedule types:
- ``fixed_interval``: windows of equal length (``interval_hours``) back
  to back from the anchor. E.g. ``interval_hours=6`` → 4 windows/day.
- ``burst``: cycles of ``burst_on_days`` (entries daily) followed by
  ``burst_off_days`` (no entries). E.g. 7 days on, 7 days off.
- ``event_triggered``: no scheduled windows — the participant initiates
  entries from the landing page. ``current_window`` always returns None;
  compliance is participant-initiated, not schedule-tracked.

All offsets use ``timedelta`` arithmetic on timezone-aware values
throughout. The functions are pure (no side effects, no ORM queries) —
the caller passes a ``menu``-like object with the needed attributes and,
for compliance, a list of entry-like objects.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable

# Default grace period in minutes: a window stays submittable for this
# long after its scheduled end. Prevents edge-case missed entries.
DEFAULT_GRACE_MINUTES = 30

# Default interval for burst "on" days when interval_hours is not set:
# one entry per day (24 hours).
_BURST_DEFAULT_INTERVAL_HOURS = 24


def anchor_time(menu: Any, *, enrolment: Any, survey_start: Any) -> Any:
    """Return the reference time for window calculations.

    Mirrors ``staged.anchor_time`` and ``delphi._anchor_time``. For the
    ``enrolment`` anchor the enrolment time is used (falling back to
    ``survey_start`` if the participant has no progress row yet — e.g.
    first access). For the ``survey_open`` anchor the survey start is
    used; if it is None the caller must surface a warning (handled in
    the organise view).
    """
    anchor_attr = getattr(menu, "anchor", "enrolment")
    if anchor_attr == "survey_open":
        return survey_start
    return enrolment or survey_start


def _interval_hours(menu: Any) -> int | None:
    """Return the effective interval for fixed_interval and burst schedules."""
    ih = getattr(menu, "interval_hours", None)
    if ih is not None:
        return int(ih)
    # burst without interval_hours → default to daily entries during on-days.
    if getattr(menu, "schedule_type", "fixed_interval") == "burst":
        return _BURST_DEFAULT_INTERVAL_HOURS
    return None


def window_for_order(menu: Any, order: int, *, anchor: Any) -> tuple[Any, Any] | None:
    """Return ``(expected_start, expected_end)`` for the ``order``-th window.

    Returns ``None`` if the schedule type does not produce a window for
    the given order (e.g. ``event_triggered`` has no scheduled windows,
    or the order falls in a burst off-period).

    For ``fixed_interval``: window N spans
    ``[anchor + N*interval, anchor + (N+1)*interval)``.

    For ``burst``: windows are numbered sequentially across on-periods
    only. Within an on-period of ``burst_on_days`` days with daily
    entries, windows are ``[anchor + offset, anchor + offset + 24h)``.
    Off-periods are skipped — window N maps to the Nth on-day, not the
    Nth calendar day.
    """
    if anchor is None:
        return None

    schedule_type = getattr(menu, "schedule_type", "fixed_interval")

    if schedule_type == "event_triggered":
        return None

    interval = _interval_hours(menu)
    if interval is None or interval <= 0:
        return None

    if schedule_type == "burst":
        on_days = int(getattr(menu, "burst_on_days", 0) or 0)
        off_days = int(getattr(menu, "burst_off_days", 0) or 0)
        if on_days <= 0:
            return None
        cycle_days = on_days + off_days
        # Each on-day has one window (daily). Window `order` maps to the
        # `order`-th on-day across cycles. We need to find which cycle
        # and which day within the cycle.
        # on-day index within all on-days = order
        # cycle_index = order // on_days
        # day_in_cycle = order % on_days
        cycle_index = order // on_days
        day_in_cycle = order % on_days
        # Absolute day offset from anchor:
        day_offset = cycle_index * cycle_days + day_in_cycle
        start = anchor + timedelta(days=day_offset)
        end = start + timedelta(hours=interval)
        return (start, end)

    # fixed_interval: windows are back-to-back from the anchor.
    start = anchor + timedelta(hours=interval * order)
    end = start + timedelta(hours=interval)
    return (start, end)


def current_window(
    menu: Any, *, anchor: Any, now: Any, grace_minutes: int | None = None
) -> tuple[int, Any, Any] | None:
    """Return ``(order, start, end)`` for the currently-open window, or ``None``.

    A window is "open" if ``now`` is in ``[start, end + grace)``. Returns
    ``None`` between windows (fixed_interval has no gaps, so None only
    happens for burst off-periods or event_triggered).

    For ``event_triggered``: always returns ``None`` (no scheduled windows).
    For ``fixed_interval``: always returns a window if the anchor is set
    and ``interval_hours > 0`` (windows are back-to-back).
    For ``burst``: returns ``None`` during off-periods.
    """
    if anchor is None:
        return None

    schedule_type = getattr(menu, "schedule_type", "fixed_interval")
    if schedule_type == "event_triggered":
        return None

    interval = _interval_hours(menu)
    if interval is None or interval <= 0:
        return None

    grace = grace_minutes
    if grace is None:
        grace = int(getattr(menu, "grace_minutes", DEFAULT_GRACE_MINUTES) or 0)

    if schedule_type == "fixed_interval":
        # Windows are back-to-back from the anchor. The current window
        # order is floor((now - anchor) / interval). If now < anchor,
        # no window is open yet.
        elapsed = now - anchor
        if elapsed.total_seconds() < 0:
            return None
        order = int(elapsed.total_seconds() // (interval * 3600))
        # Check if we're still in the grace of the previous window.
        # If so, return the previous window — the participant can still
        # submit it. This matters for back-to-back windows where window
        # N+1 has started but window N's grace hasn't expired.
        if order > 0:
            prev_win = window_for_order(menu, order - 1, anchor=anchor)
            if prev_win is not None:
                prev_end = prev_win[1]
                if now < prev_end + timedelta(minutes=grace):
                    return (order - 1, prev_win[0], prev_win[1])
        win = window_for_order(menu, order, anchor=anchor)
        if win is None:
            return None
        start, end = win
        # Window is open if now < end + grace.
        if now < end + timedelta(minutes=grace):
            return (order, start, end)
        # Past the grace of the last window → next window is open
        # (back-to-back, so this shouldn't happen unless interval is 0).
        return None

    if schedule_type == "burst":
        on_days = int(getattr(menu, "burst_on_days", 0) or 0)
        off_days = int(getattr(menu, "burst_off_days", 0) or 0)
        if on_days <= 0:
            return None
        cycle_days = on_days + off_days
        elapsed_days = (now - anchor).total_seconds() / 86400
        if elapsed_days < 0:
            return None
        day_in_cycle = int(elapsed_days) % cycle_days
        cycle_index = int(elapsed_days) // cycle_days
        # If we're in an off-period, no window is open.
        if day_in_cycle >= on_days:
            return None
        # We're in an on-day. The window for today opens at midnight
        # (anchor + day_offset days) and lasts `interval` hours.
        day_offset = cycle_index * cycle_days + day_in_cycle
        start = anchor + timedelta(days=day_offset)
        end = start + timedelta(hours=interval)
        if now < start:
            return None
        if now < end + timedelta(minutes=grace):
            order = cycle_index * on_days + day_in_cycle
            return (order, start, end)
        # Past today's window + grace → no window until tomorrow.
        return None

    return None


def next_window(menu: Any, *, anchor: Any, now: Any) -> tuple[int, Any, Any] | None:
    """Return the next upcoming window after ``now``, or ``None``.

    Used by the diary landing page to show "next entry opens at …" when
    no window is currently open.
    """
    if anchor is None:
        return None

    schedule_type = getattr(menu, "schedule_type", "fixed_interval")
    if schedule_type == "event_triggered":
        return None

    interval = _interval_hours(menu)
    if interval is None or interval <= 0:
        return None

    if schedule_type == "fixed_interval":
        elapsed = now - anchor
        if elapsed.total_seconds() < 0:
            # Before the anchor — first window is at the anchor.
            win = window_for_order(menu, 0, anchor=anchor)
            if win is not None:
                return (0, win[0], win[1])
            return None
        order = int(elapsed.total_seconds() // (interval * 3600))
        # Check current window first; if it's still open, the "next" is
        # the one after.
        cur = current_window(menu, anchor=anchor, now=now)
        if cur is not None:
            order = cur[0] + 1
        win = window_for_order(menu, order, anchor=anchor)
        if win is not None:
            return (order, win[0], win[1])
        return None

    if schedule_type == "burst":
        on_days = int(getattr(menu, "burst_on_days", 0) or 0)
        off_days = int(getattr(menu, "burst_off_days", 0) or 0)
        if on_days <= 0:
            return None
        cycle_days = on_days + off_days
        # Walk forward day by day from now until we find an on-day whose
        # window hasn't started yet (or is the current day but window
        # hasn't opened yet). Bounded by a reasonable max (2 cycles).
        for day_offset in range(0, cycle_days * 2 + 1):
            candidate_day = (now + timedelta(days=day_offset)).date()
            anchor_date = anchor.date()
            days_from_anchor = (candidate_day - anchor_date).days
            if days_from_anchor < 0:
                continue
            day_in_cycle = days_from_anchor % cycle_days
            cycle_index = days_from_anchor // cycle_days
            if day_in_cycle >= on_days:
                continue  # off-period
            start = anchor + timedelta(days=days_from_anchor)
            end = start + timedelta(hours=interval)
            if start > now:
                order = cycle_index * on_days + day_in_cycle
                return (order, start, end)
        return None

    return None


def expected_entry_count(menu: Any, *, anchor: Any, now: Any) -> int:
    """Return the total number of windows that should have opened by ``now``.

    This is the compliance denominator: the number of entries a
    participant *should* have submitted by now. For ``event_triggered``,
    returns 0 (compliance is not schedule-tracked).
    """
    if anchor is None:
        return 0

    schedule_type = getattr(menu, "schedule_type", "fixed_interval")
    if schedule_type == "event_triggered":
        return 0

    interval = _interval_hours(menu)
    if interval is None or interval <= 0:
        return 0

    elapsed = now - anchor
    if elapsed.total_seconds() < 0:
        return 0

    if schedule_type == "fixed_interval":
        # Windows are back-to-back; count = floor(elapsed / interval) + 1
        # (the +1 is the currently-open window, which the participant
        # may not have submitted yet but is expected to).
        count = int(elapsed.total_seconds() // (interval * 3600)) + 1
        return count

    if schedule_type == "burst":
        on_days = int(getattr(menu, "burst_on_days", 0) or 0)
        off_days = int(getattr(menu, "burst_off_days", 0) or 0)
        if on_days <= 0:
            return 0
        cycle_days = on_days + off_days
        elapsed_days = int(elapsed.total_seconds() // 86400)
        full_cycles = elapsed_days // cycle_days
        days_in_current_cycle = elapsed_days % cycle_days
        on_days_in_current_cycle = min(days_in_current_cycle + 1, on_days)
        # If we're in an off-period, only count the on-days from the
        # completed cycles.
        if days_in_current_cycle >= on_days:
            on_days_in_current_cycle = on_days
        count = full_cycles * on_days + on_days_in_current_cycle
        return count

    return 0


def compliance_for_progress(
    menu: Any,
    entries: Iterable[Any],
    *,
    anchor: Any,
    now: Any,
) -> dict[str, Any]:
    """Return compliance stats for a participant's diary entries.

    ``entries`` is an iterable of entry-like objects, each with:
    - ``order`` (int): the window order.
    - ``submitted_at`` (datetime or None): when the participant submitted.
    - ``is_missed`` (bool): whether the window was marked missed.

    Returns::

        {
            "expected": int,          # expected entries by now
            "submitted": int,         # entries with submitted_at set
            "missed": int,            # entries marked is_missed
            "compliance_pct": float,  # submitted / expected * 100 (0 if expected=0)
            "missed_orders": list[int],  # orders of missed entries
        }

    For ``event_triggered`` schedules, ``expected`` is 0 and
    ``compliance_pct`` is 0 (compliance is not schedule-tracked — the
    dashboard shows total submitted instead).
    """
    expected = expected_entry_count(menu, anchor=anchor, now=now)

    entry_list = list(entries)
    submitted = sum(
        1 for e in entry_list if getattr(e, "submitted_at", None) is not None
    )
    missed_entries = [e for e in entry_list if getattr(e, "is_missed", False)]
    missed = len(missed_entries)
    missed_orders = [getattr(e, "order", 0) for e in missed_entries]

    compliance_pct = 0.0
    if expected > 0:
        compliance_pct = (submitted / expected) * 100

    return {
        "expected": expected,
        "submitted": submitted,
        "missed": missed,
        "compliance_pct": compliance_pct,
        "missed_orders": missed_orders,
    }


def ensure_entry_for_current_window(
    menu: Any,
    progress: Any,
    *,
    now: Any,
    anchor: Any,
) -> Any:
    """Idempotently create/fetch the DiaryEntry for the current window.

    Called by the take view on each access. If the current window has no
    DiaryEntry row yet, create one with ``submitted_at=None``. If the
    window has closed (past grace) and the entry is still unsent, mark
    ``is_missed=True``.

    Returns the DiaryEntry (or None if no window is currently open).

    This is the one side-effecting function in ``diary.py`` — it persists
    the DiaryEntry row, mirroring ``assign_round_for_progress`` in
    ``delphi.py`` which persists the round FK on SurveyProgress.
    """
    from .models import DiaryEntry

    current = current_window(
        menu,
        anchor=anchor,
        now=now,
        grace_minutes=int(getattr(menu, "grace_minutes", DEFAULT_GRACE_MINUTES) or 0),
    )
    if current is None:
        return None
    order, expected_start, expected_end = current
    entry, _created = DiaryEntry.objects.get_or_create(
        menu=menu,
        progress=progress,
        order=order,
        defaults={
            "expected_start": expected_start,
            "expected_end": expected_end,
        },
    )
    return entry


def mark_missed_entries(menu: Any, progress: Any, *, now: Any, anchor: Any) -> int:
    """Mark DiaryEntry rows as missed if their window has closed without a submission.

    Called by the take view on each access (after ensure_entry_for_current_window).
    Returns the number of entries newly marked as missed.

    A window is "missed" when ``now >= expected_end + grace`` and
    ``submitted_at`` is None and ``is_missed`` is False. Once marked,
    ``is_missed`` stays True (idempotent).
    """
    from .models import DiaryEntry

    grace = timedelta(
        minutes=int(getattr(menu, "grace_minutes", DEFAULT_GRACE_MINUTES) or 0)
    )
    entries = DiaryEntry.objects.filter(
        menu=menu,
        progress=progress,
        submitted_at__isnull=True,
        is_missed=False,
        expected_end__lt=now - grace,
    )
    return entries.update(is_missed=True)
