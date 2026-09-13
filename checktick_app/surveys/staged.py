"""Staged layout phase-resolution helpers.

Pure, testable functions used by the take view to compute which phases are
currently open for a participant. Kept separate from the runtime pipeline
so a future Delphi round scheduler can sit next to it without touching the
take view (see docs/survey-layouts-technical.md §Staged (longitudinal)
layout §Delphi compatibility).

A phase is open at time ``now`` when::

    anchor_time + start_offset_days <= now < anchor_time + end_offset_days

``end_offset_days`` is null for an open-ended phase (never closes). The
anchor time is either the participant's enrolment time
(``SurveyProgress.created_at``) or the survey's open date
(``Survey.start_at``), per ``StagedMenu.anchor``.

All offsets are integer days. ``datetime`` arithmetic uses timezone-aware
values throughout.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from .models import StagedMenu, StagedPhase


def anchor_time(menu: StagedMenu, *, enrolment, survey_start):
    """Return the reference time for phase windows.

    ``enrolment`` is the participant's ``SurveyProgress.created_at`` and
    ``survey_start`` is ``Survey.start_at``. For the ``enrolment`` anchor
    the enrolment time is used (falling back to ``survey_start`` if the
    participant has no progress row yet — e.g. first access). For the
    ``survey_open`` anchor the survey start is used; if it is None the
    caller must surface a warning (handled in the organise view).
    """
    if menu.anchor == StagedMenu.Anchor.SURVEY_OPEN:
        return survey_start
    # ENROLMENT: prefer the participant's enrolment time; fall back to the
    # survey start (or now) when there is no progress row yet.
    return enrolment or survey_start


def is_phase_open(phase: StagedPhase, anchor, now) -> bool:
    """Return True if ``phase`` is open at ``now`` given ``anchor``.

    A phase is open when ``anchor + start <= now < anchor + end``. An
    open-ended phase (``end_offset_days`` is None) never closes.
    """
    start = anchor + timedelta(days=int(phase.start_offset_days or 0))
    if now < start:
        return False
    if phase.end_offset_days is None:
        return True
    end = anchor + timedelta(days=int(phase.end_offset_days))
    return now < end


def open_phases(menu: StagedMenu, *, enrolment, survey_start, now) -> list[StagedPhase]:
    """Return the ordered list of phases open at ``now``.

    Phases are returned in ``order, id`` sequence (the model default).
    """
    anchor = anchor_time(menu, enrolment=enrolment, survey_start=survey_start)
    if anchor is None:
        # survey_open anchor with no Survey.start_at: nothing is open.
        # The organise-view warnings flag this misconfiguration.
        return []
    return [
        phase
        for phase in menu.phases.all().order_by("order", "id")
        if is_phase_open(phase, anchor, now)
    ]


def open_group_ids(menu: StagedMenu, *, enrolment, survey_start, now) -> list[int]:
    """Return the ordered, de-duplicated group IDs from currently-open phases.

    Order follows the phase ``order, id`` sequence, then each phase's
    groups in their natural order. The take view re-orders the final set
    via ``_resolved_group_order_ids`` so the authored/Organise-page order
    is preserved; this helper only decides *which* IDs are in the set.
    """
    phases = open_phases(menu, enrolment=enrolment, survey_start=survey_start, now=now)
    seen: set[int] = set()
    out: list[int] = []
    for phase in phases:
        for gid in phase.groups.values_list("id", flat=True):
            if gid not in seen:
                seen.add(gid)
                out.append(gid)
    return out


def phases_for_group(menu: StagedMenu, group_id: int) -> Iterable[StagedPhase]:
    """Return the phases that include ``group_id`` (for overlap warnings)."""
    return menu.phases.filter(groups__id=group_id).order_by("order", "id")
