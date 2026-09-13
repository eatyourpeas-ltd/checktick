"""Matrix layout helpers.

Pure, testable functions used by the take view to compute section states
for the matrix landing page and to validate sections before marking them
complete. Kept separate from the runtime pipeline so a future Delphi round
scheduler can sit next to it without touching the take view (see
docs/survey-layouts-technical.md §Matrix (free navigation) layout
§Delphi compatibility).

A matrix survey shows all sections as cards on a landing page. The
participant navigates freely between sections and marks each complete when
done. ``SurveyProgress.completed_group_ids`` is the soft indicator; the
final ``submit_survey`` action re-validates all required questions
regardless of this list.

Section states (computed from ``partial_answers`` +
``completed_group_ids``):

- ``complete``    — in ``completed_group_ids``
- ``in_progress`` — has at least one saved answer, not in
                    ``completed_group_ids``
- ``not_started`` — no saved answers, not in ``completed_group_ids``
"""

from __future__ import annotations

from typing import Iterable

from .models import SurveyQuestion


def section_required_questions(
    survey_id: int, group_id: int
) -> Iterable[SurveyQuestion]:
    """Return the required questions for one section.

    A question is required when ``SurveyQuestion.required`` is True. Hidden
    questions (``hidden_by_default``) are excluded — they are revealed by
    branching conditions and are not required until shown.
    """
    return (
        SurveyQuestion.objects.filter(
            survey_id=survey_id,
            group_id=group_id,
            required=True,
            hidden_by_default=False,
        )
        .order_by("order", "id")
        .iterator()
    )


def section_answered_question_ids(
    partial_answers: dict, survey_id: int, group_id: int
) -> set[int]:
    """Return the IDs of questions in this section that have a saved answer.

    ``partial_answers`` is the ``SurveyProgress.partial_answers`` dict
    keyed by question ID (as a string). A value is considered "answered"
    when it is truthy and not an empty string/list/dict.
    """
    question_ids = set(
        SurveyQuestion.objects.filter(
            survey_id=survey_id, group_id=group_id
        ).values_list("id", flat=True)
    )
    answered: set[int] = set()
    for qid in question_ids:
        val = partial_answers.get(str(qid))
        if val is None:
            continue
        if isinstance(val, (list, dict, str)) and not val:
            continue
        answered.add(qid)
    return answered


def is_section_complete(progress, group_id: int) -> bool:
    """Return True if ``group_id`` is in ``progress.completed_group_ids``."""
    raw = getattr(progress, "completed_group_ids", None) or []
    if not isinstance(raw, list):
        return False
    return int(group_id) in {int(x) for x in raw if str(x).isdigit()}


def section_state(progress, survey_id: int, group_id: int) -> str:
    """Return the landing-page state for one section.

    One of ``"complete"``, ``"in_progress"``, ``"not_started"``.
    """
    if is_section_complete(progress, group_id):
        return "complete"
    answered = section_answered_question_ids(
        progress.partial_answers or {}, survey_id, group_id
    )
    if answered:
        return "in_progress"
    return "not_started"


def missing_required_question_ids(
    partial_answers: dict, survey_id: int, group_id: int
) -> list[int]:
    """Return IDs of required questions in this section that have no answer.

    Used by the ``complete_section`` action (validates before marking
    complete) and by the final ``submit_survey`` action (re-validates all
    sections regardless of ``completed_group_ids``).
    """
    answered = section_answered_question_ids(partial_answers, survey_id, group_id)
    missing: list[int] = []
    for q in section_required_questions(survey_id, group_id):
        if q.id not in answered:
            missing.append(q.id)
    return missing


def landing_card_states(progress, survey_id: int, group_ids: list[int]) -> list[dict]:
    """Return one card-state dict per group ID, in the given order.

    Each dict has: ``group_id``, ``state`` (complete/in_progress/not_started),
    ``answered_count``, ``total_questions``, ``missing_required_count``.
    The take view passes the ordered ``group_ids`` (from
    ``_resolved_group_order_ids``) so the cards follow the authored or
    participant-visit order.
    """
    cards: list[dict] = []
    for gid in group_ids:
        questions = list(
            SurveyQuestion.objects.filter(survey_id=survey_id, group_id=gid)
            .order_by("order", "id")
            .values("id", "required", "hidden_by_default")
        )
        answered = section_answered_question_ids(
            progress.partial_answers or {}, survey_id, gid
        )
        missing = missing_required_question_ids(
            progress.partial_answers or {}, survey_id, gid
        )
        cards.append(
            {
                "group_id": gid,
                "state": section_state(progress, survey_id, gid),
                "answered_count": len(answered),
                "total_questions": len(questions),
                "missing_required_count": len(missing),
            }
        )
    return cards


def all_sections_complete(progress, survey_id: int, group_ids: list[int]) -> bool:
    """Return True if every section is in ``completed_group_ids``.

    The final ``submit_survey`` action uses this as a soft check — it still
    re-validates required questions across all sections as a hard gate.
    """
    completed = {
        int(x)
        for x in (getattr(progress, "completed_group_ids", None) or [])
        if str(x).isdigit()
    }
    return all(int(gid) in completed for gid in group_ids)


def add_completed_group(progress, group_id: int) -> None:
    """Add ``group_id`` to ``progress.completed_group_ids`` (idempotent)."""
    raw = getattr(progress, "completed_group_ids", None)
    if not isinstance(raw, list):
        raw = []
    ids = {int(x) for x in raw if str(x).isdigit()}
    ids.add(int(group_id))
    progress.completed_group_ids = sorted(ids)


def remove_completed_group(progress, group_id: int) -> None:
    """Remove ``group_id`` from ``progress.completed_group_ids`` (idempotent).

    Called when the participant edits a completed section (save_draft on a
    completed section un-marks it so the landing page shows "in progress").
    """
    raw = getattr(progress, "completed_group_ids", None)
    if not isinstance(raw, list):
        raw = []
    ids = {int(x) for x in raw if str(x).isdigit()}
    ids.discard(int(group_id))
    progress.completed_group_ids = sorted(ids)
