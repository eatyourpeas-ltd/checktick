"""
Response analytics service for survey dashboards.

Computes aggregate statistics and answer distributions for visualization.
Answer content is read via load_answers(): encrypted responses require the
survey key (unlocked session) and are excluded when it is unavailable, so
dashboards for locked encrypted surveys show no distribution data.
Demographics/IMD require separate unlock and are handled elsewhere.
"""

from collections import Counter
from dataclasses import dataclass, field
import json
from typing import Any

from django.db.models import QuerySet


@dataclass
class AnswerDistribution:
    """Distribution of answers for a single question."""

    question_id: int
    question_text: str
    question_type: str
    total_responses: int
    options: list[dict[str, Any]] = field(default_factory=list)
    # Each option: {"label": str, "count": int, "percent": float}

    @property
    def options_json(self) -> str:
        """Safe JSON serialisation of options — escapes </ to prevent script break-out."""
        return json.dumps(self.options, separators=(",", ":")).replace("</", "<\\/")


@dataclass
class ResponseAnalytics:
    """Aggregate analytics for a survey's responses."""

    total_responses: int
    # Question-level distributions (for chartable question types)
    distributions: list[AnswerDistribution] = field(default_factory=list)


CHARTABLE_TYPES = {"mc_single", "mc_multi", "yesno", "likert", "dropdown"}


def compute_response_analytics(
    survey,
    responses: QuerySet | None = None,
    limit_questions: int = 10,
    survey_key: bytes | None = None,
) -> ResponseAnalytics:
    """
    Compute analytics for a survey's responses.

    Args:
        survey: Survey model instance
        responses: Optional queryset of responses (defaults to all)
        limit_questions: Max number of questions to analyze (for performance)
        survey_key: Survey decryption key (private key for submission-keypair
            surveys, KEK for legacy encrypted surveys). Required to read
            encrypted responses; responses stored encrypted are skipped when
            this is None or decryption fails.

    Returns:
        ResponseAnalytics with distributions for chartable questions
    """
    if responses is None:
        responses = survey.responses.all()

    total = responses.count()
    if total == 0:
        return ResponseAnalytics(total_responses=0, distributions=[])

    # Get chartable questions, ordered by group position (from survey.style) then by question order
    from checktick_app.surveys.views import (
        _build_repeat_config,
        _order_questions_by_group,
        _repeatable_question_ids,
    )

    all_chartable = list(
        survey.questions.filter(type__in=CHARTABLE_TYPES).select_related("group")
    )
    ordered_questions = _order_questions_by_group(survey, all_chartable)
    questions = ordered_questions[:limit_questions]

    # Identify repeatable questions so per-instance values are counted correctly.
    repeat_config = _build_repeat_config(survey)
    repeatable_qids = _repeatable_question_ids(survey, repeat_config)

    distributions = []

    for question in questions:
        dist = _compute_question_distribution(
            question,
            responses,
            is_repeatable=question.id in repeatable_qids,
            survey_key=survey_key,
        )
        if dist:
            distributions.append(dist)

    return ResponseAnalytics(total_responses=total, distributions=distributions)


def _resolve_response_answers(response, survey_key: bytes | None) -> dict | None:
    """Return a response's answers, decrypting when necessary.

    Returns None when the response is encrypted but no key is available or
    decryption fails — the response is then excluded from distributions
    rather than silently counted as empty.
    """
    if response.enc_answers:
        if not survey_key:
            return None
        try:
            return response.load_answers(survey_key)
        except Exception:
            return None
    return response.answers or {}


def _compute_question_distribution(
    question,
    responses: QuerySet,
    is_repeatable: bool = False,
    survey_key: bytes | None = None,
) -> AnswerDistribution | None:
    """Compute answer distribution for a single question.

    For repeatable questions the stored answer is a list of per-instance
    values; each instance is counted independently so the distribution
    reflects every repeat entry across all responses.
    """
    q_id = str(question.id)
    counter: Counter = Counter()
    answered_count = 0

    for response in responses.iterator():
        answers = _resolve_response_answers(response, survey_key)
        if answers is None:
            continue
        answer = answers.get(q_id)

        if answer is None or answer == "":
            continue

        # Repeatable answers are a list of per-instance values. Each instance
        # may be a scalar or (for mc_multi/orderable) a list.
        if is_repeatable:
            if not isinstance(answer, list):
                answer = [answer]
            for instance in answer:
                if instance is None or instance == "":
                    continue
                answered_count += 1
                _tally_answer(counter, question, instance)
            continue

        answered_count += 1
        _tally_answer(counter, question, answer)

    if answered_count == 0:
        return None

    # Build options list, sorted by count descending
    options = []
    for label, count in counter.most_common():
        percent = (count / answered_count * 100) if answered_count > 0 else 0
        options.append(
            {
                "label": _truncate_label(label, 50),
                "count": count,
                "percent": round(percent, 1),
            }
        )

    # For likert/dropdown, try to preserve original order from question options
    if question.type in ("likert", "dropdown", "mc_single"):
        options = _reorder_by_question_options(question, options)

    return AnswerDistribution(
        question_id=question.id,
        question_text=_truncate_label(question.text, 100),
        question_type=question.type,
        total_responses=answered_count,
        options=options,
    )


def _tally_answer(counter: Counter, question, answer) -> None:
    """Tally a single (possibly list-valued) answer into the counter."""
    if question.type == "mc_multi":
        # Multi-select: answer is a list
        if isinstance(answer, list):
            for item in answer:
                counter[str(item)] += 1
        else:
            counter[str(answer)] += 1
    elif question.type == "yesno":
        # Normalize yes/no
        val = str(answer).lower()
        if val in ("yes", "true", "1"):
            counter["Yes"] += 1
        else:
            counter["No"] += 1
    else:
        # Single value
        counter[str(answer)] += 1


def _truncate_label(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _reorder_by_question_options(question, options: list[dict]) -> list[dict]:
    """
    Reorder options to match the question's defined order.
    Falls back to count-sorted order for any options not in the definition.
    """
    opts = question.options
    if isinstance(opts, list):
        q_options = opts
    elif isinstance(opts, dict):
        q_options = opts.get("choices", [])
    else:
        q_options = []
    if not q_options:
        return options

    # Build order map from question definition
    order_map = {}
    for i, opt in enumerate(q_options):
        if isinstance(opt, dict):
            label = opt.get("label") or opt.get("value", "")
        else:
            label = str(opt)
        order_map[label] = i

    # Sort: defined options first (in order), then others by count
    def sort_key(opt):
        label = opt["label"]
        if label in order_map:
            return (0, order_map[label])
        return (1, -opt["count"])

    return sorted(options, key=sort_key)
