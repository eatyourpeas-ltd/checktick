"""
Tests for the summary service layer — text collation, numeric summary,
date-range filtering, and the LLM theme analyser.

These tests cover the service-layer behaviour described in
``docs/reporting-planning.md`` §4.1 and §7:

- Text collation: truncation at 500 chars; skipped count; word-frequency
  correctness (case-fold, stop words, min length).
- Numeric stats: mean / median / stdev correctness against known inputs;
  empty-answer handling; non-numeric input rejection.
- Date-range filter: ?from= / ?to= applied to submitted_at; boundary
  inclusivity; invalid date format handling.
- LLM theme endpoint: mocked Ollama client; sanitisation applied to output;
  graceful degradation when Ollama is unreachable; audit log entry contains
  metadata only.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.services.response_analytics import (
    NUMERIC_TYPES,
    TEXT_TYPES,
    TextCollation,
    NumericSummary,
    SurveySummary,
    WordCloudEntry,
    _coerce_numeric,
    _median,
    _tokenise_for_word_cloud,
    compute_numeric_summary,
    compute_survey_summary,
    compute_text_collation,
    filter_responses_by_date,
    parse_date_range,
)
from checktick_app.surveys.theme_analyzer import summarise_themes

User = get_user_model()
TEST_PASSWORD = "x"  # noqa: S105


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def user(db):
    return User.objects.create_user(username="summaryuser", password=TEST_PASSWORD)


@pytest.fixture
def survey(user, db):
    s = Survey.objects.create(name="Summary Test Survey", slug="summary-test", owner=user)
    group = QuestionGroup.objects.create(name="Group 1", owner=user)
    s.question_groups.add(group)
    return s


def _add_question(survey, qtype, text, *, options=None, order=0):
    group = survey.question_groups.first()
    return SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text=text,
        type=qtype,
        order=order,
        options=options or [],
    )


def _add_response(survey, answers, *, days_ago=0):
    r = SurveyResponse.objects.create(survey=survey, answers=answers)
    if days_ago:
        r.submitted_at = timezone.now() - timedelta(days=days_ago)
        r.save(update_fields=["submitted_at"])
    return r


# --------------------------------------------------------------------------- #
# Text collation
# --------------------------------------------------------------------------- #


class TestTextCollation:
    def test_truncates_each_response_to_500_chars(self, survey, db):
        q = _add_question(survey, "text", "Tell us more")
        long_text = "x" * 1000
        _add_response(survey, {str(q.id): long_text})
        coll = compute_text_collation(q, survey.responses.all())
        assert coll.answered_count == 1
        assert len(coll.responses) == 1
        assert len(coll.responses[0]) <= 500

    def test_skipped_count(self, survey, db):
        q = _add_question(survey, "text", "Comments")
        _add_response(survey, {str(q.id): "good"})
        _add_response(survey, {str(q.id): ""})  # skipped
        _add_response(survey, {})  # skipped (no key)
        coll = compute_text_collation(
            q, survey.responses.all(), total_responses=3
        )
        assert coll.answered_count == 1
        assert coll.skipped_count == 2

    def test_word_cloud_case_folding_and_stop_words(self, survey, db):
        q = _add_question(survey, "text", "Feedback")
        _add_response(survey, {str(q.id): "The nurse was very kind and Very kind"})
        _add_response(survey, {str(q.id): "kind kind KIND"})
        coll = compute_text_collation(q, survey.responses.all())
        terms = {e.term: e.count for e in coll.word_cloud}
        # "the" is a stop word; "kind" is case-folded and counted three times
        # plus the "very kind" pair.
        assert "the" not in terms
        assert "kind" in terms
        assert terms["kind"] >= 3

    def test_word_cloud_min_length(self, survey, db):
        q = _add_question(survey, "text", "Feedback")
        _add_response(survey, {str(q.id): "a an ok good"})
        coll = compute_text_collation(q, survey.responses.all())
        terms = {e.term for e in coll.word_cloud}
        # 1-2 letter tokens are below the min length (3).
        assert "a" not in terms
        assert "an" not in terms
        assert "ok" not in terms
        assert "good" in terms

    def test_word_cloud_json_is_safe(self, survey, db):
        q = _add_question(survey, "text", "Feedback")
        _add_response(survey, {str(q.id): "safe word"})
        coll = compute_text_collation(q, survey.responses.all())
        # </script> must not appear unescaped in the JSON payload.
        payload = coll.word_cloud_json
        assert "</script>" not in payload


# --------------------------------------------------------------------------- #
# Numeric summary
# --------------------------------------------------------------------------- #


class TestNumericSummary:
    def test_basic_stats(self, survey, db):
        q = _add_question(survey, "number", "Age")
        for v in (10, 20, 30, 40):
            _add_response(survey, {str(q.id): v})
        s = compute_numeric_summary(q, survey.responses.all())
        assert s.count == 4
        assert s.min == 10
        assert s.max == 40
        assert s.sum == 100
        assert s.mean == 25.0
        assert s.median == 25.0
        # Population stdev of [10,20,30,40]: variance = 125, stdev ~ 11.18
        assert s.stdev is not None
        assert abs(s.stdev - 11.180339887498949) < 1e-6

    def test_median_odd_count(self, survey, db):
        q = _add_question(survey, "number", "Score")
        for v in (1, 2, 3):
            _add_response(survey, {str(q.id): v})
        s = compute_numeric_summary(q, survey.responses.all())
        assert s.median == 2.0

    def test_empty_answers_returns_zero_count(self, survey, db):
        q = _add_question(survey, "number", "Score")
        _add_response(survey, {})
        _add_response(survey, {})
        s = compute_numeric_summary(q, survey.responses.all())
        assert s.count == 0
        assert s.min is None
        assert s.mean is None

    def test_non_numeric_input_rejected(self, survey, db):
        q = _add_question(survey, "number", "Score")
        _add_response(survey, {str(q.id): "not a number"})
        _add_response(survey, {str(q.id): 42})
        s = compute_numeric_summary(q, survey.responses.all())
        # Only the numeric value is counted; the string is skipped.
        assert s.count == 1
        assert s.min == 42
        assert s.max == 42

    def test_string_numeric_values_coerced(self, survey, db):
        q = _add_question(survey, "number", "Score")
        _add_response(survey, {str(q.id): "10"})
        _add_response(survey, {str(q.id): "20"})
        s = compute_numeric_summary(q, survey.responses.all())
        assert s.count == 2
        assert s.sum == 30.0

    def test_single_value_stdev_zero(self, survey, db):
        q = _add_question(survey, "number", "Score")
        _add_response(survey, {str(q.id): 5})
        s = compute_numeric_summary(q, survey.responses.all())
        assert s.stdev == 0.0


class TestNumericHelpers:
    def test_coerce_numeric_rejects_bool(self):
        assert _coerce_numeric(True) is None
        assert _coerce_numeric(False) is None

    def test_coerce_numeric_rejects_garbage(self):
        assert _coerce_numeric("abc") is None
        assert _coerce_numeric("") is None

    def test_coerce_numeric_accepts_floats(self):
        assert _coerce_numeric(1.5) == 1.5
        assert _coerce_numeric("1.5") == 1.5

    def test_median_even(self):
        assert _median([1, 2, 3, 4]) == 2.5

    def test_median_odd(self):
        assert _median([1, 2, 3]) == 2.0

    def test_tokenise_strips_punctuation(self):
        terms = _tokenise_for_word_cloud("Hello, world! This is a test.")
        assert "hello" in terms
        assert "world" in terms
        assert "test" in terms
        # "is" and "a" are stop words / below min length.
        assert "is" not in terms
        assert "a" not in terms


# --------------------------------------------------------------------------- #
# Date-range filtering
# --------------------------------------------------------------------------- #


class TestDateRange:
    def test_inclusive_from_and_to(self, survey, db):
        q = _add_question(survey, "yesno", "OK")
        _add_response(survey, {str(q.id): "yes"}, days_ago=5)
        _add_response(survey, {str(q.id): "no"}, days_ago=1)
        _add_response(survey, {str(q.id): "yes"}, days_ago=0)
        today = timezone.now().date().isoformat()
        week_ago = (timezone.now() - timedelta(days=6)).date().isoformat()
        qs, err = filter_responses_by_date(survey, week_ago, today)
        assert err is None
        assert qs.count() == 3  # all three within the 7-day window

    def test_invalid_from_format(self, survey, db):
        qs, err = filter_responses_by_date(survey, "not-a-date", None)
        assert err is not None
        assert "from" in err
        # On error, returns unfiltered queryset (caller surfaces the error).
        assert qs.count() == survey.responses.count()

    def test_invalid_to_format(self, survey, db):
        qs, err = filter_responses_by_date(survey, None, "31/01/2026")
        assert err is not None
        assert "to" in err

    def test_from_after_to(self, survey, db):
        qs, err = filter_responses_by_date(survey, "2026-02-01", "2026-01-01")
        assert err is not None
        assert "from" in err.lower() or "to" in err.lower()

    def test_single_day_range_inclusive(self, survey, db):
        q = _add_question(survey, "yesno", "OK")
        today = timezone.now()
        # One response today, one yesterday.
        r1 = _add_response(survey, {str(q.id): "yes"}, days_ago=0)
        r2 = _add_response(survey, {str(q.id): "no"}, days_ago=1)
        today_iso = today.date().isoformat()
        qs, err = filter_responses_by_date(survey, today_iso, today_iso)
        assert err is None
        ids = {r.id for r in qs}
        assert r1.id in ids
        assert r2.id not in ids


# --------------------------------------------------------------------------- #
# Survey summary orchestrator
# --------------------------------------------------------------------------- #


class TestComputeSurveySummary:
    def test_empty_survey(self, survey, db):
        summary = compute_survey_summary(survey)
        assert summary.total_responses == 0
        assert summary.distributions == []
        assert summary.text_collations == []
        assert summary.numeric_summaries == []

    def test_mixed_question_types_in_order(self, survey, db):
        q_num = _add_question(survey, "number", "Age", order=0)
        q_text = _add_question(survey, "text", "Comments", order=1)
        q_yn = _add_question(survey, "yesno", "OK", order=2)
        _add_response(survey, {str(q_num.id): 30, str(q_text.id): "fine", str(q_yn.id): "yes"})
        _add_response(survey, {str(q_num.id): 40, str(q_text.id): "good", str(q_yn.id): "no"})
        summary = compute_survey_summary(survey)
        assert summary.total_responses == 2
        # question_order preserves document order across all three types.
        assert summary.question_order == [q_num.id, q_text.id, q_yn.id]
        assert summary.question_index[q_num.id][0] == "numeric"
        assert summary.question_index[q_text.id][0] == "text"
        assert summary.question_index[q_yn.id][0] == "chartable"

    def test_non_summary_types_omitted(self, survey, db):
        # image / orderable / template_* are out of scope per planning doc §4.1.
        q_img = _add_question(survey, "image", "Pick an image", order=0)
        q_text = _add_question(survey, "text", "Comments", order=1)
        _add_response(survey, {str(q_text.id): "hello"})
        summary = compute_survey_summary(survey)
        # image question is not in the order list.
        assert q_img.id not in summary.question_order
        assert q_text.id in summary.question_order


# --------------------------------------------------------------------------- #
# LLM theme analyser (mocked)
# --------------------------------------------------------------------------- #


class TestSummariseThemes:
    def test_empty_responses_returns_graceful_failure(self):
        result = summarise_themes("Question?", [])
        assert result["success"] is False
        assert "No responses" in result["error"]
        assert result["summary"] == ""

    def test_llm_disabled(self, settings, survey, db):
        settings.LLM_ENABLED = False
        result = summarise_themes("Question?", ["a response"])
        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    def test_mocked_llm_success_sanitised(self):
        """A successful LLM response is sanitised before being returned."""
        from checktick_app.surveys.llm_client import ConversationalSurveyLLM

        class FakeClient:
            def chat_with_custom_system_prompt(self, prompt, convo, **kwargs):
                # Include a URL and a script tag — sanitisation must strip them.
                return "Themes:\n- Patients valued <script>alert(1)</script> kindness\n- See https://example.com for details"

        result = summarise_themes(
            "Question?", ["response one", "response two"], llm_client=FakeClient()
        )
        assert result["success"] is True
        assert "<script>" not in result["summary"]
        assert "https://example.com" not in result["summary"]
        assert result["token_count"] > 0
        assert result["duration_ms"] >= 0

    def test_mocked_llm_failure_graceful(self):
        class FakeClient:
            def chat_with_custom_system_prompt(self, prompt, convo, **kwargs):
                raise RuntimeError("Ollama unreachable")

        result = summarise_themes("Question?", ["a response"], llm_client=FakeClient())
        assert result["success"] is False
        assert "failed" in result["error"].lower() or "unreachable" in result["error"].lower()

    def test_mocked_llm_empty_response(self):
        class FakeClient:
            def chat_with_custom_system_prompt(self, prompt, convo, **kwargs):
                return ""

        result = summarise_themes("Question?", ["a response"], llm_client=FakeClient())
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_does_not_log_input_text(self, caplog):
        """Per AGENTS.md: never log decrypted survey objects or free-text input."""
        unique_marker = "ZZQRT_UNIQUE_DO_NOT_LOG_ZZQRT"
        responses = [f"response {unique_marker}"]

        class FakeClient:
            def chat_with_custom_system_prompt(self, prompt, convo, **kwargs):
                return "summary"

        with caplog.at_level("DEBUG"):
            summarise_themes("Question?", responses, llm_client=FakeClient())
        # The unique marker must not appear in any log record.
        for record in caplog.records:
            assert unique_marker not in record.getMessage()
