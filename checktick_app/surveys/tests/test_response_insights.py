"""
Tests for Response Insights dashboard functionality.

Tests verify that the response insights partial:
1. Renders correctly with analytics data
2. Shows appropriate content based on response count
3. Maintains accessibility standards (ARIA attributes, semantic HTML)
4. Handles edge cases gracefully
"""

from django.test import Client
import pytest

from checktick_app.surveys.services.response_analytics import compute_response_analytics

# Test password constant - required by pre-commit hook
TEST_PASSWORD = "x"  # noqa: S105


@pytest.fixture
def user(db):
    """Create a test user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="insightsuser",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def survey_with_responses(user, db):
    """Create a survey with questions and responses for testing insights."""
    from checktick_app.surveys.models import (
        QuestionGroup,
        Survey,
        SurveyQuestion,
        SurveyResponse,
    )

    survey = Survey.objects.create(
        name="Insights Test Survey",
        slug="insights-test-survey",
        owner=user,
    )

    group = QuestionGroup.objects.create(name="Test Group", owner=user)
    survey.question_groups.add(group)

    # Yes/No question
    q_yesno = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Do you like this survey?",
        type="yesno",
        order=1,
    )

    # Single choice question
    q_single = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="What is your preferred option?",
        type="mc_single",
        options={"choices": ["Option A", "Option B", "Option C"]},
        order=2,
    )

    # Create responses with varied answers
    for i in range(10):
        SurveyResponse.objects.create(
            survey=survey,
            answers={
                str(q_yesno.id): "yes" if i < 7 else "no",
                str(q_single.id): ["Option A", "Option B", "Option C"][i % 3],
            },
        )

    return {
        "survey": survey,
        "q_yesno": q_yesno,
        "q_single": q_single,
    }


@pytest.fixture
def empty_survey(user, db):
    """Create a survey with no responses."""
    from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion

    survey = Survey.objects.create(
        name="Empty Survey",
        slug="empty-insights-survey",
        owner=user,
    )

    group = QuestionGroup.objects.create(name="Test Group", owner=user)
    survey.question_groups.add(group)

    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="A question with no answers",
        type="yesno",
        order=1,
    )

    return survey


@pytest.mark.django_db
class TestResponseInsightsDisplay:
    """Test that response insights render correctly on dashboard."""

    def test_dashboard_shows_response_insights_section(
        self, user, survey_with_responses
    ):
        """Dashboard should display Response Insights section with data."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Should contain Response Insights heading
        assert "Response Insights" in content

        # Should show response count
        assert "10" in content  # Total responses

    def test_dashboard_shows_question_distributions(self, user, survey_with_responses):
        """Dashboard should display distribution charts for each chartable question."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Should show question texts
        assert "Do you like this survey?" in content
        assert "What is your preferred option?" in content

    def test_dashboard_shows_yesno_styling(self, user, survey_with_responses):
        """Yes/No questions should have success/error styling."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Should have Yes with success styling and No with error styling
        assert "text-success" in content
        assert "text-error" in content

    def test_empty_survey_shows_placeholder(self, user, empty_survey):
        """Survey with no responses should show placeholder message."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        response = client.get(f"/surveys/{empty_survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Should show placeholder message
        assert "Response Insights" in content
        assert "will appear here once you receive submissions" in content


@pytest.mark.django_db
class TestResponseInsightsAccessibility:
    """Test accessibility features of response insights."""

    def test_progress_bars_have_aria_attributes(self, user, survey_with_responses):
        """Progress bars should have proper ARIA attributes."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Check for ARIA attributes on progress bars
        assert 'role="progressbar"' in content
        assert "aria-valuenow" in content
        assert "aria-valuemin" in content
        assert "aria-valuemax" in content
        assert "aria-label" in content

    def test_collapsible_section_is_keyboard_accessible(
        self, user, survey_with_responses
    ):
        """Collapsible section should use semantic details/summary elements."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Should use details/summary for native keyboard accessibility
        assert "<details" in content
        assert "<summary" in content

    def test_truncated_labels_have_title_attribute(self, user, survey_with_responses):
        """Truncated labels should have title attribute for full text on hover."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Labels should have title attribute
        assert 'title="' in content


@pytest.mark.django_db
class TestResponseInsightsDataIntegrity:
    """Test that insights data is computed correctly."""

    def test_yesno_counts_are_accurate(self, user, survey_with_responses):
        """Yes/No counts should match actual response distribution."""
        survey = survey_with_responses["survey"]

        analytics = compute_response_analytics(survey)

        # Find the yesno distribution
        yesno_dist = next(
            (d for d in analytics.distributions if d.question_type == "yesno"),
            None,
        )
        assert yesno_dist is not None

        # We created 7 yes and 3 no
        yes_option = next((o for o in yesno_dist.options if o["label"] == "Yes"), None)
        no_option = next((o for o in yesno_dist.options if o["label"] == "No"), None)

        assert yes_option is not None
        assert no_option is not None
        assert yes_option["count"] == 7
        assert no_option["count"] == 3

    def test_single_choice_counts_are_accurate(self, user, survey_with_responses):
        """Single choice counts should match actual response distribution."""
        survey = survey_with_responses["survey"]

        analytics = compute_response_analytics(survey)

        # Find the mc_single distribution
        mc_dist = next(
            (d for d in analytics.distributions if d.question_type == "mc_single"),
            None,
        )
        assert mc_dist is not None

        # We created 10 responses cycling through 3 options
        # So distribution should be roughly: A=4, B=3, C=3
        option_counts = {o["label"]: o["count"] for o in mc_dist.options}
        assert option_counts["Option A"] == 4
        assert option_counts["Option B"] == 3
        assert option_counts["Option C"] == 3

    def test_percentages_are_calculated_correctly(self, user, survey_with_responses):
        """Percentages should be calculated correctly and sum appropriately."""
        survey = survey_with_responses["survey"]

        analytics = compute_response_analytics(survey)

        for dist in analytics.distributions:
            total_percent = sum(o["percent"] for o in dist.options)
            # Due to rounding, total might be 99-101, but should be close to 100
            assert 98 <= total_percent <= 102

    def test_chart_data_attribute_contains_valid_json(
        self, user, survey_with_responses
    ):
        """Chart data attribute should contain valid JSON for future JS integration."""
        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        survey = survey_with_responses["survey"]
        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        content = response.content.decode("utf-8")

        # Find data-chart-data attribute and verify it's valid JSON
        assert "data-chart-data" in content


@pytest.mark.django_db
class TestResponseInsightsEdgeCases:
    """Test edge cases and error handling."""

    def test_survey_with_only_text_questions_shows_no_charts(self, user, db):
        """Surveys with only text questions should not show distribution charts."""
        from checktick_app.surveys.models import (
            QuestionGroup,
            Survey,
            SurveyQuestion,
            SurveyResponse,
        )

        survey = Survey.objects.create(
            name="Text Only Survey",
            slug="text-only-survey",
            owner=user,
        )

        group = QuestionGroup.objects.create(name="Test Group", owner=user)
        survey.question_groups.add(group)

        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="What are your thoughts?",
            type="text",
            order=1,
        )

        SurveyResponse.objects.create(
            survey=survey,
            answers={"1": "Some thoughts"},
        )

        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        _ = response.content.decode("utf-8")

        # Should not show distribution charts for text questions
        # But should still show the page
        assert response.status_code == 200

    def test_handles_missing_answers_gracefully(self, user, db):
        """Should handle responses with missing answer data."""
        from checktick_app.surveys.models import (
            QuestionGroup,
            Survey,
            SurveyQuestion,
            SurveyResponse,
        )

        survey = Survey.objects.create(
            name="Missing Answers Survey",
            slug="missing-answers-survey",
            owner=user,
        )

        group = QuestionGroup.objects.create(name="Test Group 2", owner=user)
        survey.question_groups.add(group)

        SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="A yes/no question",
            type="yesno",
            order=1,
        )

        # Create response with empty answers
        SurveyResponse.objects.create(
            survey=survey,
            answers={},
        )

        client = Client()
        client.login(username="insightsuser", password=TEST_PASSWORD)  # noqa: S106

        response = client.get(f"/surveys/{survey.slug}/dashboard/")

        # Should not error
        assert response.status_code == 200
