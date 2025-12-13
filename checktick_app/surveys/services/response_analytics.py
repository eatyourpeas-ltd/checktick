"""
Response analytics service for survey dashboards.

Computes aggregate statistics and answer distributions for visualization.
All data returned is non-encrypted (question answers only).
Demographics/IMD require separate unlock and are handled elsewhere.
"""

from collections import Counter
from dataclasses import dataclass, field
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


@dataclass
class ResponseAnalytics:
    """Aggregate analytics for a survey's responses."""

    total_responses: int
    # Question-level distributions (for chartable question types)
    distributions: list[AnswerDistribution] = field(default_factory=list)


CHARTABLE_TYPES = {"mc_single", "mc_multi", "yesno", "likert", "dropdown"}


def compute_response_analytics(
    survey, responses: QuerySet | None = None, limit_questions: int = 10
) -> ResponseAnalytics:
    """
    Compute analytics for a survey's responses.

    Args:
        survey: Survey model instance
        responses: Optional queryset of responses (defaults to all)
        limit_questions: Max number of questions to analyze (for performance)

    Returns:
        ResponseAnalytics with distributions for chartable questions
    """
    if responses is None:
        responses = survey.responses.all()

    total = responses.count()
    if total == 0:
        return ResponseAnalytics(total_responses=0, distributions=[])

    # Get chartable questions, ordered by group position (from survey.style) then by question order
    from checktick_app.surveys.views import _order_questions_by_group

    all_chartable = list(
        survey.questions.filter(type__in=CHARTABLE_TYPES).select_related("group")
    )
    ordered_questions = _order_questions_by_group(survey, all_chartable)
    questions = ordered_questions[:limit_questions]

    distributions = []

    for question in questions:
        dist = _compute_question_distribution(question, responses)
        if dist:
            distributions.append(dist)

    return ResponseAnalytics(total_responses=total, distributions=distributions)


def _compute_question_distribution(
    question, responses: QuerySet
) -> AnswerDistribution | None:
    """Compute answer distribution for a single question."""
    q_id = str(question.id)
    counter: Counter = Counter()
    answered_count = 0

    for response in responses.iterator():
        answers = response.answers or {}
        answer = answers.get(q_id)

        if answer is None or answer == "":
            continue

        answered_count += 1

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
    q_options = (question.options or {}).get("choices", [])
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
