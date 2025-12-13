"""
Tests for response analytics service.
"""

import pytest

from checktick_app.surveys.services.response_analytics import (
    AnswerDistribution,
    ResponseAnalytics,
    _reorder_by_question_options,
    _truncate_label,
    compute_response_analytics,
)


class TestTruncateLabel:
    """Tests for label truncation helper."""

    def test_short_label_unchanged(self):
        assert _truncate_label("Short", 50) == "Short"

    def test_exact_length_unchanged(self):
        text = "x" * 50
        assert _truncate_label(text, 50) == text

    def test_long_label_truncated(self):
        text = "x" * 60
        result = _truncate_label(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_empty_string(self):
        assert _truncate_label("", 50) == ""


class TestReorderByQuestionOptions:
    """Tests for option reordering."""

    def test_reorder_to_match_question_options(self):
        """Options should be reordered to match question definition."""

        class MockQuestion:
            options = {"choices": ["First", "Second", "Third"]}

        options = [
            {"label": "Third", "count": 5, "percent": 50},
            {"label": "First", "count": 3, "percent": 30},
            {"label": "Second", "count": 2, "percent": 20},
        ]

        result = _reorder_by_question_options(MockQuestion(), options)

        assert result[0]["label"] == "First"
        assert result[1]["label"] == "Second"
        assert result[2]["label"] == "Third"

    def test_unknown_options_sorted_by_count(self):
        """Options not in question definition should be sorted by count."""

        class MockQuestion:
            options = {"choices": ["Known"]}

        options = [
            {"label": "Unknown2", "count": 3, "percent": 30},
            {"label": "Known", "count": 5, "percent": 50},
            {"label": "Unknown1", "count": 7, "percent": 70},
        ]

        result = _reorder_by_question_options(MockQuestion(), options)

        # Known first, then unknowns by count descending
        assert result[0]["label"] == "Known"
        assert result[1]["label"] == "Unknown1"  # Higher count
        assert result[2]["label"] == "Unknown2"

    def test_no_question_options_unchanged(self):
        """If question has no options, return original order."""

        class MockQuestion:
            options = {}

        options = [
            {"label": "C", "count": 1, "percent": 10},
            {"label": "A", "count": 5, "percent": 50},
        ]

        result = _reorder_by_question_options(MockQuestion(), options)
        assert result == options

    def test_dict_style_choices(self):
        """Should handle dict-style choices with label/value keys."""

        class MockQuestion:
            options = {
                "choices": [
                    {"label": "Option A", "value": "a"},
                    {"label": "Option B", "value": "b"},
                ]
            }

        options = [
            {"label": "Option B", "count": 10, "percent": 50},
            {"label": "Option A", "count": 10, "percent": 50},
        ]

        result = _reorder_by_question_options(MockQuestion(), options)
        assert result[0]["label"] == "Option A"
        assert result[1]["label"] == "Option B"


class TestResponseAnalyticsDataclasses:
    """Tests for analytics dataclasses."""

    def test_answer_distribution_defaults(self):
        dist = AnswerDistribution(
            question_id=1,
            question_text="Test?",
            question_type="mc_single",
            total_responses=10,
        )
        assert dist.options == []

    def test_response_analytics_defaults(self):
        analytics = ResponseAnalytics(total_responses=0)
        assert analytics.distributions == []


@pytest.mark.django_db
class TestComputeResponseAnalytics:
    """Integration tests for compute_response_analytics."""

    def test_empty_survey_returns_zero_responses(self):
        """Survey with no responses should return empty analytics."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import Survey

        User = get_user_model()
        TEST_PASSWORD = "x"  # noqa: S105
        user = User.objects.create_user(
            username="analyticsuser", password=TEST_PASSWORD
        )
        survey = Survey.objects.create(
            name="Analytics Test Survey",
            slug="analytics-test",
            owner=user,
        )

        analytics = compute_response_analytics(survey)

        assert analytics.total_responses == 0
        assert analytics.distributions == []

    def test_non_chartable_questions_excluded(self):
        """Text questions should not appear in distributions."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion

        User = get_user_model()
        TEST_PASSWORD = "x"  # noqa: S105
        user = User.objects.create_user(
            username="analyticsuser2", password=TEST_PASSWORD
        )
        survey = Survey.objects.create(
            name="Text Only Survey",
            slug="text-only",
            owner=user,
        )
        group = QuestionGroup.objects.create(name="Group 1", owner=user)
        survey.question_groups.add(group)
        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="What is your name?",
            type="text",
            order=0,
        )

        analytics = compute_response_analytics(survey)

        # No chartable questions = no distributions
        assert analytics.distributions == []

    def test_mc_single_distribution_computed(self):
        """Multiple choice single should have distribution computed."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import (
            QuestionGroup,
            Survey,
            SurveyQuestion,
            SurveyResponse,
        )

        User = get_user_model()
        TEST_PASSWORD = "x"  # noqa: S105
        user = User.objects.create_user(
            username="analyticsuser3", password=TEST_PASSWORD
        )
        survey = Survey.objects.create(
            name="MC Survey",
            slug="mc-survey",
            owner=user,
        )
        group = QuestionGroup.objects.create(name="Group 1", owner=user)
        survey.question_groups.add(group)
        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Pick one",
            type="mc_single",
            order=0,
            options={"choices": ["A", "B", "C"]},
        )

        # Create responses
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "A"})
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "A"})
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "B"})

        analytics = compute_response_analytics(survey)

        assert analytics.total_responses == 3
        assert len(analytics.distributions) == 1

        dist = analytics.distributions[0]
        assert dist.question_id == question.id
        assert dist.total_responses == 3
        # A has 2 votes (66.7%), B has 1 vote (33.3%)
        assert len(dist.options) == 2
        # Options should be in question order (A, B, C), but only A and B have votes
        assert dist.options[0]["label"] == "A"
        assert dist.options[0]["count"] == 2
        assert dist.options[1]["label"] == "B"
        assert dist.options[1]["count"] == 1

    def test_yesno_normalized(self):
        """Yes/No answers should be normalized."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import (
            QuestionGroup,
            Survey,
            SurveyQuestion,
            SurveyResponse,
        )

        User = get_user_model()
        TEST_PASSWORD = "x"  # noqa: S105
        user = User.objects.create_user(
            username="analyticsuser4", password=TEST_PASSWORD
        )
        survey = Survey.objects.create(
            name="YesNo Survey",
            slug="yesno-survey",
            owner=user,
        )
        group = QuestionGroup.objects.create(name="Group 1", owner=user)
        survey.question_groups.add(group)
        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Do you agree?",
            type="yesno",
            order=0,
        )

        # Various yes/no formats
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "yes"})
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "Yes"})
        SurveyResponse.objects.create(survey=survey, answers={str(question.id): "no"})

        analytics = compute_response_analytics(survey)
        dist = analytics.distributions[0]

        # Should normalize to Yes/No
        yes_opt = next(o for o in dist.options if o["label"] == "Yes")
        no_opt = next(o for o in dist.options if o["label"] == "No")

        assert yes_opt["count"] == 2
        assert no_opt["count"] == 1

    def test_mc_multi_counts_each_selection(self):
        """Multi-select should count each selected option."""
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import (
            QuestionGroup,
            Survey,
            SurveyQuestion,
            SurveyResponse,
        )

        User = get_user_model()
        TEST_PASSWORD = "x"  # noqa: S105
        user = User.objects.create_user(
            username="analyticsuser5", password=TEST_PASSWORD
        )
        survey = Survey.objects.create(
            name="Multi Survey",
            slug="multi-survey",
            owner=user,
        )
        group = QuestionGroup.objects.create(name="Group 1", owner=user)
        survey.question_groups.add(group)
        question = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="Select all that apply",
            type="mc_multi",
            order=0,
            options={"choices": ["Red", "Green", "Blue"]},
        )

        # Response 1: Red, Green
        SurveyResponse.objects.create(
            survey=survey, answers={str(question.id): ["Red", "Green"]}
        )
        # Response 2: Green, Blue
        SurveyResponse.objects.create(
            survey=survey, answers={str(question.id): ["Green", "Blue"]}
        )

        analytics = compute_response_analytics(survey)
        dist = analytics.distributions[0]

        # Green appears in both responses
        green_opt = next(o for o in dist.options if o["label"] == "Green")
        assert green_opt["count"] == 2

        # Red and Blue appear once each
        red_opt = next(o for o in dist.options if o["label"] == "Red")
        blue_opt = next(o for o in dist.options if o["label"] == "Blue")
        assert red_opt["count"] == 1
        assert blue_opt["count"] == 1
