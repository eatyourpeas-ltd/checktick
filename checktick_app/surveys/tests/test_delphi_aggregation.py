"""Tests for the Delphi response aggregation helpers.

These tests verify the pure ``aggregate_responses_by_group`` function and
its per-type sub-aggregators in isolation, before any Delphi-specific
model or runtime hook is added. This is the one Delphi-critical pattern
that no earlier layout exercised (the RCT arm preview only filters
questions; no layout has collected responses across participants and
computed medians/IQRs/distributions before).

The round-scheduling functions (``current_round``, ``next_round``,
``assign_round_for_progress``) reference models that do not exist yet
(``DelphiMenu``, ``DelphiRound``) and are tested later when those models
are added.
"""

import pytest

from checktick_app.surveys.delphi import (
    _aggregate_categorical,
    _aggregate_numeric,
    _aggregate_text,
    _percentile,
    aggregate_responses_by_group,
)

# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_single_value(self):
        assert _percentile([5.0], 50) == 5.0
        assert _percentile([5.0], 25) == 5.0
        assert _percentile([5.0], 75) == 5.0

    def test_two_values_median(self):
        assert _percentile([1.0, 3.0], 50) == 2.0

    def test_four_values_q1_q3(self):
        # [1, 2, 3, 4] — Q1=1.75, Q3=3.25 (linear interpolation)
        assert _percentile([1.0, 2.0, 3.0, 4.0], 25) == 1.75
        assert _percentile([1.0, 2.0, 3.0, 4.0], 75) == 3.25

    def test_five_values(self):
        # [1, 2, 3, 4, 5] — Q1=2, median=3, Q3=4
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 25) == 2.0
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 75) == 4.0

    def test_ten_values(self):
        vals = [float(i) for i in range(1, 11)]
        # [1..10] — Q1=3.25, median=5.5, Q3=7.75
        assert _percentile(vals, 25) == 3.25
        assert _percentile(vals, 50) == 5.5
        assert _percentile(vals, 75) == 7.75


# ---------------------------------------------------------------------------
# _aggregate_numeric
# ---------------------------------------------------------------------------


class TestAggregateNumeric:
    class _MockQuestion:
        def __init__(self, qtype="likert"):
            self.type = qtype

    def test_likert_basic(self):
        q = self._MockQuestion("likert")
        result = _aggregate_numeric(q, [3, 4, 5, 2, 3, 4, 5, 1, 3, 4])
        assert result["question_type"] == "likert"
        assert result["count"] == 10
        assert result["median"] == 3.5
        assert result["min"] == 1
        assert result["max"] == 5
        assert result["q1"] == 3.0
        assert result["q3"] == 4.0
        assert "distribution" in result
        assert result["distribution"]["3"] == 3

    def test_number_floats(self):
        q = self._MockQuestion("number")
        result = _aggregate_numeric(q, [1.5, 2.5, 3.5, 4.5])
        assert result["count"] == 4
        assert result["median"] == 3.0
        assert result["min"] == 1.5
        assert result["max"] == 4.5

    def test_rejects_non_numeric(self):
        q = self._MockQuestion("number")
        result = _aggregate_numeric(q, [5, "not a number", 3, None, 7])
        assert result["count"] == 3
        assert result["min"] == 3
        assert result["max"] == 7

    def test_empty_after_coercion(self):
        q = self._MockQuestion("number")
        result = _aggregate_numeric(q, ["abc", None, ""])
        assert result["count"] == 0

    def test_single_value(self):
        q = self._MockQuestion("likert")
        result = _aggregate_numeric(q, [4])
        assert result["count"] == 1
        assert result["median"] == 4.0
        assert result["stdev"] == 0.0

    def test_repeatable_list_values(self):
        q = self._MockQuestion("likert")
        result = _aggregate_numeric(q, [[3, 4, 5], [2, 3]])
        assert result["count"] == 5
        assert result["median"] == 3.0

    def test_mean_and_stdev(self):
        q = self._MockQuestion("number")
        result = _aggregate_numeric(q, [2, 4, 4, 4, 5, 5, 7, 9])
        assert result["mean"] == 5.0
        assert result["stdev"] == pytest.approx(2.0, abs=0.01)


# ---------------------------------------------------------------------------
# _aggregate_categorical
# ---------------------------------------------------------------------------


class TestAggregateCategorical:
    class _MockQuestion:
        def __init__(self, qtype):
            self.type = qtype

    def test_mc_single_distribution_and_mode(self):
        q = self._MockQuestion("mc_single")
        result = _aggregate_categorical(q, ["A", "A", "B", "C", "A"])
        assert result["count"] == 5
        assert result["distribution"]["A"] == 3
        assert result["distribution"]["B"] == 1
        assert result["distribution"]["C"] == 1
        assert result["mode"] == "A"

    def test_mc_multi_distribution(self):
        q = self._MockQuestion("mc_multi")
        result = _aggregate_categorical(q, [["A", "B"], ["A"], ["B", "C"]])
        assert result["count"] == 5  # total selections, not responses
        assert result["distribution"]["A"] == 2
        assert result["distribution"]["B"] == 2
        assert result["distribution"]["C"] == 1

    def test_yesno_counts_and_pct(self):
        q = self._MockQuestion("yesno")
        result = _aggregate_categorical(q, ["yes", "yes", "no", "yes", "no"])
        assert result["count"] == 5
        assert result["yes_count"] == 3
        assert result["no_count"] == 2
        assert result["dont_know_count"] == 0
        assert result["yes_pct"] == 60.0

    def test_yesno_with_dont_know(self):
        q = self._MockQuestion("yesno")
        result = _aggregate_categorical(
            q, ["yes", "no", "dont_know", "don't know", "dk"]
        )
        assert result["yes_count"] == 1
        assert result["no_count"] == 1
        assert result["dont_know_count"] == 3

    def test_dropdown(self):
        q = self._MockQuestion("dropdown")
        result = _aggregate_categorical(q, ["X", "Y", "X", "X"])
        assert result["count"] == 4
        assert result["distribution"]["X"] == 3
        assert result["mode"] == "X"

    def test_empty(self):
        q = self._MockQuestion("mc_single")
        result = _aggregate_categorical(q, [])
        assert result["count"] == 0
        assert result["distribution"] == {}


# ---------------------------------------------------------------------------
# _aggregate_text
# ---------------------------------------------------------------------------


class TestAggregateText:
    def test_collects_strings(self):
        result = _aggregate_text(["hello", "world", "foo"])
        assert result["question_type"] == "text"
        assert result["count"] == 3
        assert result["responses"] == ["hello", "world", "foo"]

    def test_handles_repeatable_lists(self):
        result = _aggregate_text([["a", "b"], ["c"]])
        assert result["count"] == 3
        assert result["responses"] == ["a", "b", "c"]

    def test_skips_blank(self):
        result = _aggregate_text(["hello", "", "  ", "world"])
        assert result["count"] == 2
        assert result["responses"] == ["hello", "world"]

    def test_empty(self):
        result = _aggregate_text([])
        assert result["count"] == 0
        assert result["responses"] == []

    def test_safety_cap(self):
        # Generate more than the cap to verify it's enforced.
        from checktick_app.surveys.delphi import _MAX_TEXT_RESPONSES_PER_QUESTION

        values = [f"response {i}" for i in range(_MAX_TEXT_RESPONSES_PER_QUESTION + 50)]
        result = _aggregate_text(values)
        assert result["count"] == _MAX_TEXT_RESPONSES_PER_QUESTION


# ---------------------------------------------------------------------------
# aggregate_responses_by_group (integration)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAggregateResponsesByGroup:
    """Integration tests using the real Django models."""

    TEST_PASSWORD = "x"

    @pytest.fixture
    def owner(self, django_user_model):
        return django_user_model.objects.create_user(
            username="delphi_owner@example.com", password=self.TEST_PASSWORD
        )

    @pytest.fixture
    def org(self, owner):
        from checktick_app.surveys.models import Organization

        return Organization.objects.create(name="Org", owner=owner)

    @pytest.fixture
    def survey(self, owner, org):
        from checktick_app.surveys.models import Survey

        return Survey.objects.create(
            owner=owner,
            organization=org,
            name="Delphi Test",
            slug="delphi-test",
        )

    @pytest.fixture
    def group(self, survey, owner):
        from checktick_app.surveys.models import QuestionGroup

        g = QuestionGroup.objects.create(name="Round 1", owner=owner)
        survey.question_groups.add(g)
        return g

    def test_empty_group_ids(self, survey):
        result = aggregate_responses_by_group(survey.id, [])
        assert result == {}

    def test_no_responses(self, survey, group):
        result = aggregate_responses_by_group(survey.id, [group.id])
        # Group exists but has no questions or responses
        assert result == {}

    def test_likert_aggregation(self, survey, group, owner):
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Rate importance",
            type="likert",
            order=0,
            options={"choices": ["1", "2", "3", "4", "5"]},
        )
        for val in [3, 4, 5, 2, 3, 4, 5, 1, 3, 4]:
            SurveyResponse.objects.create(survey=survey, answers={str(q.id): val})

        result = aggregate_responses_by_group(survey.id, [group.id])
        assert group.id in result
        assert q.id in result[group.id]
        stats = result[group.id][q.id]
        assert stats["question_type"] == "likert"
        assert stats["count"] == 10
        assert stats["median"] == 3.5
        assert "q1" in stats
        assert "q3" in stats
        assert "distribution" in stats

    def test_yesno_aggregation(self, survey, group, owner):
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Agree?",
            type="yesno",
            order=0,
        )
        for val in ["yes", "yes", "no", "yes", "no"]:
            SurveyResponse.objects.create(survey=survey, answers={str(q.id): val})

        result = aggregate_responses_by_group(survey.id, [group.id])
        stats = result[group.id][q.id]
        assert stats["question_type"] == "yesno"
        assert stats["yes_count"] == 3
        assert stats["no_count"] == 2
        assert stats["yes_pct"] == 60.0

    def test_long_text_aggregation(self, survey, group, owner):
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Explain your reasoning",
            type="long_text",
            order=0,
        )
        texts = ["First response", "Second response", "Third response"]
        for text in texts:
            SurveyResponse.objects.create(survey=survey, answers={str(q.id): text})

        result = aggregate_responses_by_group(survey.id, [group.id])
        stats = result[group.id][q.id]
        assert stats["question_type"] == "text"
        assert stats["count"] == 3
        assert stats["responses"] == texts

    def test_content_block_skipped(self, survey, group, owner):
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Content block",
            type="content_block",
            order=0,
            options={"heading": "", "body_md": ""},
        )
        SurveyResponse.objects.create(survey=survey, answers={})

        result = aggregate_responses_by_group(survey.id, [group.id])
        # Content block should not appear in results
        assert q.id not in result.get(group.id, {})

    def test_multiple_groups(self, survey, owner):
        from checktick_app.surveys.models import (
            QuestionGroup,
            SurveyQuestion,
            SurveyResponse,
        )

        g1 = QuestionGroup.objects.create(name="G1", owner=owner)
        g2 = QuestionGroup.objects.create(name="G2", owner=owner)
        survey.question_groups.add(g1, g2)

        q1 = SurveyQuestion.objects.create(
            survey=survey,
            group=g1,
            text="Q1",
            type="likert",
            order=0,
        )
        q2 = SurveyQuestion.objects.create(
            survey=survey,
            group=g2,
            text="Q2",
            type="yesno",
            order=0,
        )

        SurveyResponse.objects.create(
            survey=survey,
            answers={str(q1.id): 3, str(q2.id): "yes"},
        )
        SurveyResponse.objects.create(
            survey=survey,
            answers={str(q1.id): 4, str(q2.id): "no"},
        )

        result = aggregate_responses_by_group(survey.id, [g1.id, g2.id])
        assert g1.id in result
        assert g2.id in result
        assert q1.id in result[g1.id]
        assert q2.id in result[g2.id]
        assert result[g1.id][q1.id]["question_type"] == "likert"
        assert result[g2.id][q2.id]["question_type"] == "yesno"

    def test_filtered_responses(self, survey, group, owner):
        """The ``responses`` parameter scopes the aggregation to a subset."""
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Q",
            type="likert",
            order=0,
        )
        # Create 5 responses
        for val in [1, 2, 3, 4, 5]:
            SurveyResponse.objects.create(survey=survey, answers={str(q.id): val})

        # Pass only the first 2 responses
        subset = list(SurveyResponse.objects.all()[:2])
        result = aggregate_responses_by_group(survey.id, [group.id], responses=subset)
        stats = result[group.id][q.id]
        assert stats["count"] == 2

    def test_blank_answers_excluded(self, survey, group, owner):
        from checktick_app.surveys.models import SurveyQuestion, SurveyResponse

        q = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Q",
            type="likert",
            order=0,
        )
        SurveyResponse.objects.create(survey=survey, answers={str(q.id): 3})
        SurveyResponse.objects.create(survey=survey, answers={str(q.id): ""})
        SurveyResponse.objects.create(survey=survey, answers={})

        result = aggregate_responses_by_group(survey.id, [group.id])
        stats = result[group.id][q.id]
        assert stats["count"] == 1
