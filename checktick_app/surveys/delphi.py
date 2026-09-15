"""Delphi consensus-round helpers.

This module provides the pure functions the Delphi layout (see
``docs/survey-layouts-technical.md`` §Delphi (consensus rounds) — full
design) uses for:

- **Response aggregation** — collecting responses across participants and
  computing per-question aggregate statistics (medians, IQRs,
  distributions, free-text collation). This is the one Delphi-critical
  pattern that no earlier layout exercised; it is tested in isolation
  here before any Delphi-specific model or runtime hook is added.
- **Round scheduling** — ``current_round``, ``next_round``,
  ``assign_round_for_progress``. These mirror ``staged.py``'s phase
  helpers and sit next to them without touching staged.

The module is deliberately free of side effects (except
``assign_round_for_progress`` which persists the round FK on
``SurveyProgress``). It never calls the LLM directly — qualitative
thematic analysis is done by the view layer via
``theme_analyzer.summarise_themes()`` after ``aggregate_responses_by_group``
has collected the free-text responses.

Security notes:
- ``aggregate_responses_by_group`` receives decrypted answers via the
  ``survey_key`` parameter. The caller (the view) is responsible for the
  unlock gate — this function must only be called after the survey has
  been unlocked.
- The function never logs answer content. It logs metadata only
  (question id, response count) per the medical-app logging rules.
- Free-text responses collected for LLM thematic analysis are returned
  to the caller; they are never persisted by this module.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import logging
import statistics
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from .services.response_analytics import (
    _coerce_numeric,
    _is_blank_answer,
    _resolve_response_answers,
)

logger = logging.getLogger(__name__)

# Question types that produce numeric/ordinal values suitable for
# median/IQR computation. Likert is ordinal but treated as numeric for
# Delphi consensus reporting (the standard approach in Delphi methodology).
_NUMERIC_AGGREGATE_TYPES = {"likert", "number"}

# Question types that produce categorical distributions.
_CATEGORICAL_TYPES = {"mc_single", "mc_multi", "dropdown", "yesno"}

# Question types that produce free-text responses for LLM thematic analysis.
_TEXT_TYPES = {"text", "long_text"}

# Maximum number of free-text responses to collect per question for LLM
# thematic analysis. The LLM has a token budget; sending thousands of
# long responses would exceed it. The caller may further truncate before
# calling ``summarise_themes``. This cap is a safety bound, not a target.
_MAX_TEXT_RESPONSES_PER_QUESTION = 200


# ---------------------------------------------------------------------------
# Response aggregation
# ---------------------------------------------------------------------------


def aggregate_responses_by_group(
    survey_id: int,
    group_ids: list[int],
    *,
    survey_key: bytes | None = None,
    responses: QuerySet | list | None = None,
) -> dict[int, dict[int, dict[str, Any]]]:
    """Collect and aggregate responses for the given groups.

    Returns a nested dict: ``{group_id: {question_id: stats}}``.

    Per question type:

    - ``likert`` / ``number``: ``median``, ``q1``, ``q3``, ``min``,
      ``max``, ``count``, ``distribution`` (value → count).
    - ``mc_single`` / ``dropdown``: ``distribution`` (label → count),
      ``mode``, ``count``.
    - ``mc_multi``: ``distribution`` (option → count), ``count``.
    - ``yesno``: ``yes_count``, ``no_count``, ``dont_know_count``,
      ``yes_pct``, ``count``.
    - ``long_text`` / ``text``: ``responses`` (list of strings, for LLM
      thematic analysis), ``count``.
    - ``content_block``: skipped (no answer).

    ``survey_key`` is the survey's decryption key (KEK or private key,
    depending on the encryption path). Required when responses are
    encrypted; ``None`` for plaintext-only surveys.

    ``responses`` is an optional pre-filtered queryset or list of
    ``SurveyResponse`` objects. When ``None``, all completed responses
    for the survey are used. Delphi passes a round-scoped subset so the
    aggregation reflects only the relevant round's submissions.

    The function is pure (no side effects, no LLM calls). It reads
    decrypted answers via the existing ``_resolve_response_answers``
    helper (the same path the CSV export and summary report use).
    """
    from .models import SurveyQuestion, SurveyResponse

    if not group_ids:
        return {}

    # Resolve the response set.
    if responses is None:
        responses = SurveyResponse.objects.filter(survey_id=survey_id)
    # Materialise once — we iterate per question and don't want to re-query.
    response_list = list(responses)

    # Prefetch questions for the target groups, ordered by group then order.
    questions = (
        SurveyQuestion.objects.filter(group_id__in=group_ids, survey_id=survey_id)
        .select_related("group")
        .order_by("group_id", "order", "id")
    )

    result: dict[int, dict[int, dict[str, Any]]] = {}
    for q in questions:
        gid = q.group_id
        if gid not in result:
            result[gid] = {}
        stats = _aggregate_single_question(q, response_list, survey_key)
        if stats is not None:
            result[gid][q.id] = stats
    return result


def _aggregate_single_question(
    question, responses: list, survey_key: bytes | None
) -> dict[str, Any] | None:
    """Compute aggregate stats for one question across the given responses.

    Returns ``None`` if the question type is not aggregatable (e.g.
    ``content_block``) or if no responses have answers for this question.
    """
    q_type = question.type
    q_id = str(question.id)

    if q_type == "content_block":
        return None

    # Collect raw answer values from all responses.
    raw_values: list[Any] = []
    for response in responses:
        answers = _resolve_response_answers(response, survey_key)
        if answers is None:
            continue
        answer = answers.get(q_id)
        if _is_blank_answer(answer):
            continue
        raw_values.append(answer)

    if not raw_values:
        return {"question_type": q_type, "count": 0}

    if q_type in _NUMERIC_AGGREGATE_TYPES:
        return _aggregate_numeric(question, raw_values)
    if q_type in _CATEGORICAL_TYPES:
        return _aggregate_categorical(question, raw_values)
    if q_type in _TEXT_TYPES:
        return _aggregate_text(raw_values)
    # Unknown type — return a count only.
    return {"question_type": q_type, "count": len(raw_values)}


def _aggregate_numeric(question, raw_values: list[Any]) -> dict[str, Any]:
    """Aggregate numeric/likert responses: median, IQR, distribution."""
    # Coerce to floats, rejecting non-numeric values.
    numeric_values: list[float] = []
    distribution: Counter = Counter()
    for value in raw_values:
        # Handle repeatable answers (list of instances).
        if isinstance(value, list):
            for instance in value:
                parsed = _coerce_numeric(instance)
                if parsed is not None:
                    numeric_values.append(parsed)
                    distribution[str(instance)] += 1
            continue
        parsed = _coerce_numeric(value)
        if parsed is not None:
            numeric_values.append(parsed)
            distribution[str(value)] += 1

    if not numeric_values:
        return {"question_type": question.type, "count": 0}

    sorted_vals = sorted(numeric_values)
    n = len(sorted_vals)
    median = statistics.median(sorted_vals)
    q1 = _percentile(sorted_vals, 25)
    q3 = _percentile(sorted_vals, 75)

    return {
        "question_type": question.type,
        "count": n,
        "median": round(median, 2),
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "mean": round(statistics.mean(numeric_values), 2),
        "stdev": round(statistics.pstdev(numeric_values), 2) if n > 1 else 0.0,
        "distribution": dict(distribution.most_common()),
    }


def _aggregate_categorical(question, raw_values: list[Any]) -> dict[str, Any]:
    """Aggregate categorical responses: frequency distribution, mode."""
    counter: Counter = Counter()
    count = 0
    for value in raw_values:
        if question.type == "mc_multi":
            if isinstance(value, list):
                for item in value:
                    counter[str(item)] += 1
                    count += 1
            else:
                counter[str(value)] += 1
                count += 1
        elif question.type == "yesno":
            val = str(value).lower()
            if val in ("yes", "true", "1"):
                counter["yes"] += 1
            elif val in ("dont_know", "don't know", "dontknow", "dk"):
                counter["dont_know"] += 1
            else:
                counter["no"] += 1
            count += 1
        else:
            counter[str(value)] += 1
            count += 1

    result: dict[str, Any] = {
        "question_type": question.type,
        "count": count,
        "distribution": dict(counter.most_common()),
    }

    if question.type == "yesno":
        yes = counter.get("yes", 0)
        no = counter.get("no", 0)
        dk = counter.get("dont_know", 0)
        total = yes + no + dk
        result["yes_count"] = yes
        result["no_count"] = no
        result["dont_know_count"] = dk
        result["yes_pct"] = round(yes / total * 100, 1) if total > 0 else 0.0
    elif counter:
        result["mode"] = counter.most_common(1)[0][0]

    return result


def _aggregate_text(raw_values: list[Any]) -> dict[str, Any]:
    """Aggregate free-text responses: collect strings for LLM thematic analysis.

    The responses are returned untruncated — the caller (the view) is
    responsible for truncating before sending to the LLM if needed. A
    safety cap of ``_MAX_TEXT_RESPONSES_PER_QUESTION`` is applied to
    prevent excessive memory use; the caller may further filter.
    """
    collected: list[str] = []
    for value in raw_values:
        if isinstance(value, list):
            for instance in value:
                if _is_blank_answer(instance):
                    continue
                collected.append(str(instance))
        else:
            if _is_blank_answer(value):
                continue
            collected.append(str(value))
        if len(collected) >= _MAX_TEXT_RESPONSES_PER_QUESTION:
            break

    return {
        "question_type": "text",
        "count": len(collected),
        "responses": collected,
    }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the ``pct``-th percentile of a sorted list (linear interpolation).

    Uses the same method as NumPy's default (linear interpolation between
    the closest ranks). ``sorted_values`` must be non-empty and pre-sorted.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (n - 1)
    lower = int(rank)
    upper = min(lower + 1, n - 1)
    frac = rank - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * frac


# ---------------------------------------------------------------------------
# Round scheduling (used by the runtime hook — models not yet built)
# ---------------------------------------------------------------------------

# The functions below reference ``DelphiMenu`` and ``DelphiRound`` which
# do not exist yet. They are included here as the design specification
# and will be activated when the models are added. The runtime hook
# (``_handle_participant_submission``) will call ``assign_round_for_progress``
# in the same way it calls ``_assign_arm_for_progress`` for RCT.


def current_round(menu, *, enrolment, survey_start, now) -> Any:
    """Return the currently-open round, or ``None`` if no round is open.

    A round is open when:

    - ``opened_at`` is set and ``closed_at`` is not (manual open/close
      overrides window offsets), **or**
    - the round's window is open: ``anchor + start <= now < anchor + end``
      (and neither ``opened_at`` nor ``closed_at`` is set).

    ``menu`` is a ``DelphiMenu`` (or compatible). ``enrolment`` is the
    participant's ``SurveyProgress.created_at``; ``survey_start`` is
    ``Survey.start_at``. ``now`` is the current time.
    """
    anchor = _anchor_time(menu, enrolment=enrolment, survey_start=survey_start)
    if anchor is None:
        return None

    for rnd in menu.rounds.order_by("order", "id"):
        # Manual override takes precedence.
        if rnd.opened_at and not rnd.closed_at:
            if now >= rnd.opened_at:
                return rnd
            continue
        if rnd.closed_at:
            continue
        # Window-based.
        start = anchor + timedelta(days=int(rnd.start_offset_days or 0))
        if now < start:
            continue
        if rnd.end_offset_days is None:
            return rnd
        end = anchor + timedelta(days=int(rnd.end_offset_days))
        if now < end:
            return rnd
    return None


def next_round(menu, progress) -> Any:
    """Return the next round the participant should advance to.

    Looks at ``progress.delphi_round`` (the current assigned round) and
    returns the next round by order. Returns ``None`` if the participant
    is on the last round.
    """
    current = getattr(progress, "delphi_round", None)
    if current is None:
        return None
    rounds = list(menu.rounds.order_by("order", "id"))
    try:
        idx = rounds.index(current)
    except ValueError:
        return None
    if idx + 1 < len(rounds):
        return rounds[idx + 1]
    return None


def assign_round_for_progress(progress, menu, *, now=None) -> Any:
    """Assign and persist the current round for ``progress``.

    Idempotent: if ``progress.delphi_round`` is already set and still
    open, returns it. If the assigned round has closed, advances to the
    next open round. If no round is open, returns ``None`` (participant
    sees a "check back later" page, like Staged).

    ``now`` defaults to ``timezone.now()``.
    """
    if now is None:
        now = timezone.now()

    enrolment = progress.created_at
    survey_start = getattr(progress.survey, "start_at", None)

    current = getattr(progress, "delphi_round", None)
    if current is not None:
        # Check if the assigned round is still open.
        if current.closed_at:
            # Advance to the next open round.
            nxt = next_round(menu, progress)
            if nxt is not None:
                progress.delphi_round = nxt
                progress.save(update_fields=["delphi_round"])
                return nxt
            return None
        return current

    # No round assigned yet — find the current open round.
    rnd = current_round(menu, enrolment=enrolment, survey_start=survey_start, now=now)
    if rnd is not None:
        progress.delphi_round = rnd
        progress.save(update_fields=["delphi_round"])
    return rnd


def _anchor_time(menu, *, enrolment, survey_start):
    """Return the reference time for round windows.

    Mirrors ``staged.anchor_time``. For the ``enrolment`` anchor the
    enrolment time is used (falling back to ``survey_start`` if the
    participant has no progress row yet). For the ``survey_open`` anchor
    the survey start is used; if it is ``None`` the caller must surface
    a warning.
    """
    anchor_attr = getattr(menu, "anchor", "enrolment")
    if anchor_attr == "survey_open":
        return survey_start
    return enrolment or survey_start
