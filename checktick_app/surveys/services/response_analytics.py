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
import math
import re
from typing import Any

from django.db.models import QuerySet

# Reuses the CSV export's suffix→label mapping for follow-up inputs so both
# surfaces report follow-up text with the same configured labels.
from .export_service import _question_followup_labels

# Question types that get a bar-chart distribution.
CHARTABLE_TYPES = {"mc_single", "mc_multi", "yesno", "likert", "dropdown"}
# Question types whose answers are free text (collated + word cloud).
TEXT_TYPES = {"text", "textarea"}
# Question types whose answers are numeric (summary statistics).
NUMERIC_TYPES = {"number"}

# Truncation limit for individual free-text responses in the summary view.
# Per planning doc §4.1: truncate to ~500 chars each.
TEXT_RESPONSE_TRUNCATION = 500

# Word-cloud tuning (planning doc §3.4): case-folded, stop-word filtered,
# min-length threshold. Keep the list conservative and language-neutral enough
# for English free text; the cloud is a frequency visualisation, not analysis.
WORD_CLOUD_MIN_LENGTH = 3
WORD_CLOUD_MAX_TERMS = 60
_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "any",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "his",
        "how",
        "its",
        "may",
        "own",
        "too",
        "who",
        "him",
        "she",
        "that",
        "this",
        "with",
        "have",
        "from",
        "they",
        "will",
        "would",
        "there",
        "their",
        "what",
        "when",
        "where",
        "which",
        "your",
        "were",
        "been",
        "than",
        "then",
        "them",
        "these",
        "those",
        "about",
        "into",
        "some",
        "such",
        "only",
        "also",
        "more",
        "most",
        "very",
        "just",
        "like",
        "make",
        "made",
        "want",
        "well",
        "because",
        "should",
        "could",
        "does",
        "done",
    }
)


@dataclass
class AnswerDistribution:
    """Distribution of answers for a single question."""

    question_id: int
    question_text: str
    question_type: str
    total_responses: int
    options: list[dict[str, Any]] = field(default_factory=list)
    # Each option: {"label": str, "count": int, "percent": float}
    # Follow-up free text collected for this question (per-option, yes/no, or
    # the question-level box). Each entry: {"label": str, "text": str}
    followups: list[dict[str, str]] = field(default_factory=list)

    @property
    def options_json(self) -> str:
        """Safe JSON serialisation of options — escapes </ to prevent script break-out."""
        return json.dumps(self.options, separators=(",", ":")).replace("</", "<\\/")


@dataclass
class WordCloudEntry:
    """A single weighted term in the word cloud payload."""

    term: str
    count: int


@dataclass
class TextCollation:
    """Collated free-text answers for a single text/textarea question.

    Per planning doc §4.1: a list of responses (truncated to ~500 chars each),
    answered/skipped counts, and a tokenised word-frequency list for the
    client-side word cloud. The LLM theme summary is populated lazily by the
    separate themes endpoint and is never stored here (session-scoped only).
    """

    question_id: int
    question_text: str
    question_type: str
    answered_count: int = 0
    skipped_count: int = 0
    responses: list[str] = field(default_factory=list)
    word_cloud: list[WordCloudEntry] = field(default_factory=list)

    @property
    def word_cloud_json(self) -> str:
        """Safe JSON serialisation of the word cloud payload."""
        payload = [{"term": e.term, "count": e.count} for e in self.word_cloud]
        return json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")


@dataclass
class NumericSummary:
    """Summary statistics for a single numeric question.

    Per planning doc §4.1: count, min, max, mean, median, sum, stdev — computed
    in pure Python, no patient data leaves the DB layer. ``None`` for any stat
    that cannot be computed (empty, or no parseable numeric answers).
    """

    question_id: int
    question_text: str
    question_type: str
    count: int = 0
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    sum: float | None = None
    stdev: float | None = None

    @property
    def summary_json(self) -> str:
        """Safe JSON serialisation of the summary stats."""
        payload = {
            "count": self.count,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "median": self.median,
            "sum": self.sum,
            "stdev": self.stdev,
        }
        return json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")


@dataclass
class LLMThemeSummary:
    """Lazy LLM theme summary for a single text/textarea question.

    Per planning doc §4.1 and §3.3: only populated when the user explicitly
    requests it per question (separate endpoint). Session-scoped only — never
    written back into enc_answers. The raw LLM output is sanitised through the
    existing ``sanitize_markdown()`` pipeline by the view before being stored
    here.
    """

    question_id: int
    question_text: str
    question_type: str
    summary_markdown: str = ""
    token_count: int = 0
    model_name: str = ""
    duration_ms: int = 0
    success: bool = False
    error: str = ""


@dataclass
class SurveySummary:
    """Aggregate summary for a survey's responses, across all question types.

    Mirrors :class:`ResponseAnalytics` but covers every question type in
    document order, not just the chartable slice. Designed to be rendered by
    ``surveys/summary.html`` and shared with the dashboard insights partial
    where applicable.
    """

    total_responses: int
    distributions: list[AnswerDistribution] = field(default_factory=list)
    text_collations: list[TextCollation] = field(default_factory=list)
    numeric_summaries: list[NumericSummary] = field(default_factory=list)
    question_order: list[int] = field(default_factory=list)
    # Map question_id -> ("chartable", index) / ("text", index) / ("numeric", index)
    # so the template can render each question in document order regardless of type.
    question_index: dict[int, tuple[str, int]] = field(default_factory=dict)


@dataclass
class ResponseAnalytics:
    """Aggregate analytics for a survey's responses."""

    total_responses: int
    # Question-level distributions (for chartable question types)
    distributions: list[AnswerDistribution] = field(default_factory=list)


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
    followups: list[dict[str, str]] = []

    for response in responses.iterator():
        answers = _resolve_response_answers(response, survey_key)
        if answers is None:
            continue

        # Collect follow-up free text (stored under "{qid}_followup") so it is
        # reported alongside the distribution. Labels come from the question's
        # follow-up configuration (option index / yes/no / "any" suffix).
        fu_labels = _question_followup_labels(question)
        if fu_labels:
            fu_values = answers.get(f"{q_id}_followup")
            if isinstance(fu_values, dict):
                for suffix, text in fu_values.items():
                    if _is_blank_answer(text):
                        continue
                    followups.append(
                        {
                            "label": fu_labels.get(str(suffix), str(suffix)),
                            "text": _truncate_label(
                                str(text), TEXT_RESPONSE_TRUNCATION
                            ),
                        }
                    )

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
        followups=followups,
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


# ---------------------------------------------------------------------------
# Summary view — date-range filtering, text collation, numeric summary
# ---------------------------------------------------------------------------


def parse_date_range(
    date_from: str | None, date_to: str | None
) -> tuple[Any | None, Any | None, str | None]:
    """Parse ``?from=&to=`` ISO date query params into datetimes.

    Per planning doc §4.2: ISO date, applied to ``submitted_at``. The ``from``
    bound is inclusive at 00:00:00 of that day; the ``to`` bound is inclusive
    through 23:59:59.999999 of that day. Returns ``(start, end, error)`` where
    ``error`` is a human-readable message when the inputs are invalid (caller
    surfaces it as a 400), and ``start``/``end`` are timezone-aware datetimes
    suitable for ``__gte`` / ``__lte`` queries.
    """
    from datetime import datetime, time

    from django.utils import timezone

    start: Any | None = None
    end: Any | None = None

    if date_from:
        try:
            d = datetime.strptime(date_from.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None, None, ("Invalid 'from' date format. Use YYYY-MM-DD.")
        start = timezone.make_aware(datetime.combine(d, time.min))

    if date_to:
        try:
            d = datetime.strptime(date_to.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None, None, ("Invalid 'to' date format. Use YYYY-MM-DD.")
        # Inclusive end-of-day so a single-day range (from=to=2026-01-01)
        # captures the whole day's submissions.
        end = timezone.make_aware(datetime.combine(d, time.max))

    if start and end and start > end:
        return None, None, ("'from' date must be earlier than or equal to 'to' date.")

    return start, end, None


def filter_responses_by_date(
    survey, date_from: str | None, date_to: str | None
) -> tuple[Any, str | None]:
    """Return ``(responses_queryset, error)`` filtered by ``submitted_at``.

    On invalid input, returns the unfiltered queryset and an error message so
    the caller can render a 400 / inline warning without crashing.
    """
    start, end, err = parse_date_range(date_from, date_to)
    if err:
        return survey.responses.all(), err
    qs = survey.responses.all()
    if start:
        qs = qs.filter(submitted_at__gte=start)
    if end:
        qs = qs.filter(submitted_at__lte=end)
    return qs, None


def _is_blank_answer(value: Any) -> bool:
    """Return True if an answer value should be treated as skipped/empty."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _tokenise_for_word_cloud(text: str) -> list[str]:
    """Tokenise free text into word-cloud terms.

    Case-folded, stop-word filtered, min-length threshold (planning doc §3.4).
    Returns a list of terms (with duplicates) suitable for ``Counter``.
    """
    if not text:
        return []
    # Split on non-letter runs. Apostrophes inside words (don't, patient's)
    # are collapsed to keep the term shape simple.
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    return [
        t for t in tokens if len(t) >= WORD_CLOUD_MIN_LENGTH and t not in _STOP_WORDS
    ]


def compute_text_collation(
    question,
    responses: QuerySet,
    is_repeatable: bool = False,
    survey_key: bytes | None = None,
    total_responses: int | None = None,
) -> TextCollation:
    """Compute a :class:`TextCollation` for a single text/textarea question.

    ``total_responses`` is the total response count used to compute the
    skipped count; if ``None`` it is derived from ``responses``.
    """
    q_id = str(question.id)
    collected: list[str] = []
    answered = 0
    word_counter: Counter = Counter()

    for response in responses.iterator():
        answers = _resolve_response_answers(response, survey_key)
        if answers is None:
            continue
        answer = answers.get(q_id)

        if _is_blank_answer(answer):
            continue

        if is_repeatable:
            if not isinstance(answer, list):
                answer = [answer]
            for instance in answer:
                if _is_blank_answer(instance):
                    continue
                text_value = str(instance)
                answered += 1
                collected.append(_truncate_label(text_value, TEXT_RESPONSE_TRUNCATION))
                word_counter.update(_tokenise_for_word_cloud(text_value))
            continue

        answered += 1
        text_value = str(answer)
        collected.append(_truncate_label(text_value, TEXT_RESPONSE_TRUNCATION))
        word_counter.update(_tokenise_for_word_cloud(text_value))

    total = total_responses if total_responses is not None else responses.count()
    skipped = max(0, total - answered)

    word_cloud = [
        WordCloudEntry(term=term, count=count)
        for term, count in word_counter.most_common(WORD_CLOUD_MAX_TERMS)
        if count >= 1
    ]

    return TextCollation(
        question_id=question.id,
        question_text=_truncate_label(question.text, 100),
        question_type=question.type,
        answered_count=answered,
        skipped_count=skipped,
        responses=collected,
        word_cloud=word_cloud,
    )


def compute_numeric_summary(
    question,
    responses: QuerySet,
    is_repeatable: bool = False,
    survey_key: bytes | None = None,
) -> NumericSummary:
    """Compute a :class:`NumericSummary` for a single number question.

    Non-numeric values are rejected (skipped, not coerced) so a free-text
    answer in a numeric question does not skew the stats. ``stdev`` is the
    population standard deviation (÷n); for n=1 it is 0.0.
    """
    q_id = str(question.id)
    values: list[float] = []

    for response in responses.iterator():
        answers = _resolve_response_answers(response, survey_key)
        if answers is None:
            continue
        answer = answers.get(q_id)
        if _is_blank_answer(answer):
            continue

        if is_repeatable:
            if not isinstance(answer, list):
                answer = [answer]
            for instance in answer:
                if _is_blank_answer(instance):
                    continue
                parsed = _coerce_numeric(instance)
                if parsed is not None:
                    values.append(parsed)
            continue

        parsed = _coerce_numeric(answer)
        if parsed is not None:
            values.append(parsed)

    if not values:
        return NumericSummary(
            question_id=question.id,
            question_text=_truncate_label(question.text, 100),
            question_type=question.type,
            count=0,
        )

    n = len(values)
    s = sum(values)
    mean = s / n
    median = _median(values)
    if n > 1:
        variance = sum((v - mean) ** 2 for v in values) / n
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0

    return NumericSummary(
        question_id=question.id,
        question_text=_truncate_label(question.text, 100),
        question_type=question.type,
        count=n,
        min=min(values),
        max=max(values),
        mean=mean,
        median=median,
        sum=s,
        stdev=stdev,
    )


def _coerce_numeric(value: Any) -> float | None:
    """Coerce a stored answer to a float, returning None if non-numeric."""
    if value is None:
        return None
    if isinstance(value, bool):  # bools are ints in Python; reject them
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    """Return the median of a non-empty list of floats."""
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def compute_survey_summary(
    survey,
    responses: QuerySet | None = None,
    survey_key: bytes | None = None,
) -> SurveySummary:
    """Compute a full :class:`SurveySummary` across all question types.

    Renders every question in document order (not just the chartable slice of
    10). Encrypted responses are excluded when ``survey_key`` is None or
    decryption fails — the summary shows the questions with zero/empty stats
    in that case rather than failing, mirroring the dashboard's unlock-gated
    behaviour.
    """
    from checktick_app.surveys.views import (
        _build_repeat_config,
        _order_questions_by_group,
        _repeatable_question_ids,
    )

    if responses is None:
        responses = survey.responses.all()

    total = responses.count()
    summary = SurveySummary(total_responses=total)

    if total == 0:
        return summary

    all_questions = list(survey.questions.select_related("group").all())
    ordered_questions = _order_questions_by_group(survey, all_questions)

    repeat_config = _build_repeat_config(survey)
    repeatable_qids = _repeatable_question_ids(survey, repeat_config)

    for question in ordered_questions:
        q_type = question.type
        if q_type in CHARTABLE_TYPES:
            dist = _compute_question_distribution(
                question,
                responses,
                is_repeatable=question.id in repeatable_qids,
                survey_key=survey_key,
            )
            if dist is not None:
                summary.question_index[question.id] = (
                    "chartable",
                    len(summary.distributions),
                )
                summary.distributions.append(dist)
                summary.question_order.append(question.id)
        elif q_type in TEXT_TYPES:
            coll = compute_text_collation(
                question,
                responses,
                is_repeatable=question.id in repeatable_qids,
                survey_key=survey_key,
                total_responses=total,
            )
            summary.question_index[question.id] = (
                "text",
                len(summary.text_collations),
            )
            summary.text_collations.append(coll)
            summary.question_order.append(question.id)
        elif q_type in NUMERIC_TYPES:
            num = compute_numeric_summary(
                question,
                responses,
                is_repeatable=question.id in repeatable_qids,
                survey_key=survey_key,
            )
            summary.question_index[question.id] = (
                "numeric",
                len(summary.numeric_summaries),
            )
            summary.numeric_summaries.append(num)
            summary.question_order.append(question.id)
        # Other question types (image, orderable, template_*) are out of scope
        # for the summary view per planning doc §4.1 — they remain in the CSV
        # export only. They are omitted from ``question_order`` so the template
        # does not render a stub for them.

    return summary
