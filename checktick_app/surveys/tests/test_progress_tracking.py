"""
Tests for survey progress tracking feature.

Tests cover:
- Progress saving for authenticated users
- Progress saving for anonymous users (session-based)
- Progress restoration when returning to survey
- Token-based survey progress and expiry
- Preventing duplicate submissions
- Auto-deletion of progress on submission
- Cleanup of expired progress records
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.management.commands.cleanup_survey_progress import (
    Command as CleanupCommand,
)
from checktick_app.surveys.models import (
    Organization,
    Survey,
    SurveyAccessToken,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"
User = get_user_model()


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable rate limiting for all tests in this module."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def survey_owner(django_user_model):
    """Create a survey owner user."""
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def participant(django_user_model):
    """Create a participant user."""
    return django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def another_participant(django_user_model):
    """Create another participant user."""
    return django_user_model.objects.create_user(
        username="another@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def test_organization(survey_owner):
    """Create a test organization."""
    return Organization.objects.create(
        name="Test Organization",
        owner=survey_owner,
    )


@pytest.fixture
def published_survey(survey_owner, test_organization):
    """Create a published survey with multiple questions."""
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Test Survey",
        slug="test-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        organization=test_organization,
    )

    # Add multiple questions
    SurveyQuestion.objects.create(
        survey=survey,
        text="What is your name?",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text="What is your age?",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=1,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text="Choose one:",
        type=SurveyQuestion.Types.MULTIPLE_CHOICE_SINGLE,
        required=False,
        order=2,
    )

    return survey


@pytest.fixture
def public_survey(survey_owner, test_organization):
    """Create a public survey for anonymous testing."""
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Public Survey",
        slug="public-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
        organization=test_organization,
    )

    SurveyQuestion.objects.create(
        survey=survey,
        text="Question 1",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        text="Question 2",
        type=SurveyQuestion.Types.TEXT,
        required=False,
        order=1,
    )

    return survey


@pytest.fixture
def token_survey(survey_owner, test_organization):
    """Create a token-based survey."""
    survey = Survey.objects.create(
        owner=survey_owner,
        name="Token Survey",
        slug="token-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
        organization=test_organization,
    )

    SurveyQuestion.objects.create(
        survey=survey,
        text="Token question",
        type=SurveyQuestion.Types.TEXT,
        required=True,
        order=0,
    )

    return survey


# ============================================================================
# Authenticated User Progress Tests
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedProgress:
    """Tests for progress tracking with authenticated users."""

    def test_progress_saved_for_authenticated_user(
        self, client, published_survey, participant
    ):
        """Progress should be saved when authenticated user submits draft."""
        client.login(username="participant@example.com", password=TEST_PASSWORD)

        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
        questions = published_survey.questions.all()

        # Save draft
        response = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "John Doe",
                f"q_{questions[1].id}": "30",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "progress" in data

        # Verify progress record created
        progress = SurveyProgress.objects.get(
            survey=published_survey, user=participant
        )
        assert progress.answered_count == 2
        assert progress.total_questions == 3
        assert progress.partial_answers[f"q_{questions[0].id}"] == "John Doe"
        assert progress.partial_answers[f"q_{questions[1].id}"] == "30"

    def test_progress_restored_on_return(
        self, client, published_survey, participant
    ):
        """Previously saved answers should be restored when user returns."""
        questions = published_survey.questions.all()

        # Create existing progress
        SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={
                f"q_{questions[0].id}": "Jane Smith",
                f"q_{questions[1].id}": "25",
            },
            current_question_id=questions[1].id,
            total_questions=3,
            answered_count=2,
            expires_at=timezone.now() + timedelta(days=30),
        )

        client.login(username="participant@example.com", password=TEST_PASSWORD)
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
        response = client.get(url)

        assert response.status_code == 200
        context = response.context

        # Check progress context
        assert context["has_progress"] is True
        assert context["progress_percentage"] == 66  # 2/3 * 100
        assert context["progress_answered"] == 2
        assert context["progress_total"] == 3

        # Check answers are in context
        saved_answers = context["saved_answers"]
        assert saved_answers[f"q_{questions[0].id}"] == "Jane Smith"
        assert saved_answers[f"q_{questions[1].id}"] == "25"

    def test_progress_deleted_on_submission(
        self, client, published_survey, participant
    ):
        """Progress should be deleted when survey is successfully submitted."""
        questions = published_survey.questions.all()

        # Create existing progress
        SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={f"q_{questions[0].id}": "Test"},
            current_question_id=questions[0].id,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() + timedelta(days=30),
        )

        client.login(username="participant@example.com", password=TEST_PASSWORD)
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})

        # Submit complete survey
        response = client.post(
            url,
            {
                f"q_{questions[0].id}": "Complete Name",
                f"q_{questions[1].id}": "35",
            },
        )

        # Should redirect to thank you page
        assert response.status_code == 302
        assert "/thank-you/" in response.url

        # Progress should be deleted
        assert not SurveyProgress.objects.filter(
            survey=published_survey, user=participant
        ).exists()

    def test_one_progress_per_user_per_survey(
        self, client, published_survey, participant
    ):
        """Should only allow one progress record per user per survey."""
        questions = published_survey.questions.all()

        # Create initial progress
        progress1 = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={f"q_{questions[0].id}": "First"},
            current_question_id=questions[0].id,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() + timedelta(days=30),
        )

        client.login(username="participant@example.com", password=TEST_PASSWORD)
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})

        # Save draft again - should update, not create new
        response = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Updated",
                f"q_{questions[1].id}": "40",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200

        # Should still be only one progress record
        assert SurveyProgress.objects.filter(
            survey=published_survey, user=participant
        ).count() == 1

        # Should be updated
        progress1.refresh_from_db()
        assert progress1.partial_answers[f"q_{questions[0].id}"] == "Updated"
        assert progress1.answered_count == 2

    def test_different_users_have_separate_progress(
        self, client, published_survey, participant, another_participant
    ):
        """Different users should have independent progress records."""
        questions = published_survey.questions.all()

        # User 1 saves progress
        client.login(username="participant@example.com", password=TEST_PASSWORD)
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
        client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "User One",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        client.logout()

        # User 2 saves different progress
        client.login(username="another@example.com", password=TEST_PASSWORD)
        client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "User Two",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should have 2 separate progress records
        assert SurveyProgress.objects.filter(survey=published_survey).count() == 2

        progress1 = SurveyProgress.objects.get(
            survey=published_survey, user=participant
        )
        progress2 = SurveyProgress.objects.get(
            survey=published_survey, user=another_participant
        )

        assert progress1.partial_answers[f"q_{questions[0].id}"] == "User One"
        assert progress2.partial_answers[f"q_{questions[0].id}"] == "User Two"


# ============================================================================
# Anonymous User Progress Tests (Session-based)
# ============================================================================


@pytest.mark.django_db
class TestAnonymousProgress:
    """Tests for progress tracking with anonymous users using sessions."""

    def test_progress_saved_for_anonymous_user(self, client, public_survey):
        """Progress should be saved for anonymous users using session key."""
        url = reverse("surveys:take", kwargs={"slug": public_survey.slug})
        questions = public_survey.questions.all()

        # Anonymous user saves draft
        response = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Anonymous Answer",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify progress record created with session key
        session_key = client.session.session_key
        progress = SurveyProgress.objects.get(
            survey=public_survey, session_key=session_key
        )
        assert progress.user is None
        assert progress.answered_count == 1

    def test_anonymous_progress_restored_same_session(self, client, public_survey):
        """Anonymous user should see their progress in the same session."""
        questions = public_survey.questions.all()

        # First request to establish session
        url = reverse("surveys:take", kwargs={"slug": public_survey.slug})
        client.get(url)
        session_key = client.session.session_key

        # Create progress with this session
        SurveyProgress.objects.create(
            survey=public_survey,
            session_key=session_key,
            partial_answers={f"q_{questions[0].id}": "Saved Answer"},
            current_question_id=questions[0].id,
            total_questions=2,
            answered_count=1,
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Get survey again
        response = client.get(url)

        assert response.status_code == 200
        context = response.context
        assert context["has_progress"] is True
        assert context["saved_answers"][f"q_{questions[0].id}"] == "Saved Answer"

    def test_different_sessions_have_separate_progress(self, client, public_survey):
        """Different anonymous sessions should have independent progress."""
        questions = list(public_survey.questions.all())
        url = reverse("surveys:take", kwargs={"slug": public_survey.slug})

        # Session 1
        response1 = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Session 1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert response1.status_code == 200
        session1_key = client.session.session_key

        # Verify session 1 progress
        progress1 = SurveyProgress.objects.get(
            survey=public_survey, session_key=session1_key
        )
        assert f"q_{questions[0].id}" in progress1.partial_answers

        # Clear session to simulate new browser
        client.session.flush()

        # Session 2
        response2 = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Session 2",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert response2.status_code == 200
        session2_key = client.session.session_key

        # Should have 2 separate progress records
        assert SurveyProgress.objects.filter(survey=public_survey).count() == 2

        progress1.refresh_from_db()
        progress2 = SurveyProgress.objects.get(
            survey=public_survey, session_key=session2_key
        )

        assert progress1.partial_answers[f"q_{questions[0].id}"] == "Session 1"
        assert progress2.partial_answers[f"q_{questions[0].id}"] == "Session 2"


# ============================================================================
# Token-Based Survey Progress Tests
# ============================================================================


@pytest.mark.django_db
class TestTokenProgress:
    """Tests for progress tracking with token-based surveys."""

    def test_progress_saved_with_token(self, client, token_survey, survey_owner):
        """Progress should be saved for token-based survey access."""
        token = SurveyAccessToken.objects.create(
            survey=token_survey,
            token="valid-token",
            created_by=survey_owner,
        )

        url = reverse(
            "surveys:take_token",
            kwargs={"slug": token_survey.slug, "token": token.token},
        )
        questions = token_survey.questions.all()

        # Save draft
        response = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Token Answer",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200

        # Verify progress created
        session_key = client.session.session_key
        progress = SurveyProgress.objects.get(
            survey=token_survey,
            session_key=session_key,
            access_token=token,
        )
        assert progress.answered_count == 1

    def test_token_cannot_be_used_twice(self, client, token_survey, survey_owner):
        """Used tokens should not allow access to survey."""
        token = SurveyAccessToken.objects.create(
            survey=token_survey,
            token="onetime-token",
            created_by=survey_owner,
        )

        url = reverse(
            "surveys:take_token",
            kwargs={"slug": token_survey.slug, "token": token.token},
        )
        questions = token_survey.questions.all()

        # First submission - complete survey
        response = client.post(
            url,
            {f"q_{questions[0].id}": "Complete Answer"},
        )

        # Should redirect to thank you
        assert response.status_code == 302
        assert "/thank-you/" in response.url

        # Token should be marked as used
        token.refresh_from_db()
        assert token.used_at is not None

        # Try to access again with same token
        response = client.get(url)

        # Should redirect to closed page
        assert response.status_code == 302
        assert "/closed/" in response.url
        assert "reason=token_used" in response.url

        # Should not be able to save progress
        response = client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Should not save",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should redirect, not save
        assert response.status_code == 302

    def test_expired_token_cannot_save_progress(
        self, client, token_survey, survey_owner
    ):
        """Expired tokens should not allow saving progress."""
        # Create expired token
        token = SurveyAccessToken.objects.create(
            survey=token_survey,
            token="expired-token",
            created_by=survey_owner,
            expires_at=timezone.now() - timedelta(days=1),
        )

        url = reverse(
            "surveys:take_token",
            kwargs={"slug": token_survey.slug, "token": token.token},
        )

        # Try to access with expired token
        response = client.get(url)

        # Should redirect to closed page
        assert response.status_code == 302
        assert "/closed/" in response.url


# ============================================================================
# Permission Tests
# ============================================================================


@pytest.mark.django_db
class TestProgressPermissions:
    """Tests for ensuring users can only access their own progress."""

    def test_authenticated_user_cannot_see_other_user_progress(
        self, client, published_survey, participant, another_participant
    ):
        """Users should only see their own progress, not other users'."""
        questions = published_survey.questions.all()

        # Create progress for another user
        SurveyProgress.objects.create(
            survey=published_survey,
            user=another_participant,
            partial_answers={f"q_{questions[0].id}": "Other User Answer"},
            current_question_id=questions[0].id,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() + timedelta(days=30),
        )

        # Login as different user
        client.login(username="participant@example.com", password=TEST_PASSWORD)
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
        response = client.get(url)

        assert response.status_code == 200
        context = response.context

        # Should not see other user's progress
        assert context.get("has_progress") is False
        assert not context.get("saved_answers")

    def test_only_logged_in_user_can_access_authenticated_survey(
        self, client, published_survey, participant
    ):
        """Anonymous users should not access authenticated surveys."""
        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})

        # Try to access without login
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302
        assert "/accounts/login/" in response.url


# ============================================================================
# Progress Cleanup Tests
# ============================================================================


@pytest.mark.django_db
class TestProgressCleanup:
    """Tests for automatic cleanup of expired progress records."""

    def test_cleanup_deletes_expired_progress(self, published_survey, participant):
        """Expired progress should be deleted by cleanup command."""
        # Create expired progress (>30 days old)
        old_progress = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={"q_1": "old"},
            current_question_id=1,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() - timedelta(days=31),
        )

        # Create recent progress
        recent_progress = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={"q_2": "recent"},
            current_question_id=2,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() + timedelta(days=29),
        )

        # Run cleanup
        command = CleanupCommand()
        command.handle(dry_run=False, verbose=False)

        # Old should be deleted
        assert not SurveyProgress.objects.filter(id=old_progress.id).exists()

        # Recent should remain
        assert SurveyProgress.objects.filter(id=recent_progress.id).exists()

    def test_cleanup_dry_run_does_not_delete(self, published_survey, participant):
        """Dry run should not delete any records."""
        old_progress = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={"q_1": "old"},
            current_question_id=1,
            total_questions=3,
            answered_count=1,
            expires_at=timezone.now() - timedelta(days=31),
        )

        # Run cleanup in dry-run mode
        command = CleanupCommand()
        command.handle(dry_run=True, verbose=False)

        # Should still exist
        assert SurveyProgress.objects.filter(id=old_progress.id).exists()

    def test_progress_expires_after_30_days(self, client, published_survey, participant):
        """New progress should have 30-day expiry."""
        client.login(username="participant@example.com", password=TEST_PASSWORD)

        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})
        questions = published_survey.questions.all()

        # Save draft
        client.post(
            url,
            {
                "action": "save_draft",
                f"q_{questions[0].id}": "Test",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Check expiry
        progress = SurveyProgress.objects.get(
            survey=published_survey, user=participant
        )

        # Should expire in approximately 30 days
        time_until_expiry = progress.expires_at - timezone.now()
        assert 29 <= time_until_expiry.days <= 30


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


@pytest.mark.django_db
class TestProgressEdgeCases:
    """Tests for edge cases and error handling."""

    def test_progress_percentage_calculation(self, published_survey, participant):
        """Progress percentage should be calculated correctly."""
        progress = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={},
            current_question_id=1,
            total_questions=3,
            answered_count=2,
        )

        assert progress.calculate_progress_percentage() == 66

    def test_progress_percentage_zero_questions(self, published_survey, participant):
        """Should handle zero questions gracefully."""
        progress = SurveyProgress.objects.create(
            survey=published_survey,
            user=participant,
            partial_answers={},
            current_question_id=1,
            total_questions=0,
            answered_count=0,
        )

        assert progress.calculate_progress_percentage() == 0

    def test_empty_draft_save(self, client, published_survey, participant):
        """Should handle saving empty draft without errors."""
        client.login(username="participant@example.com", password=TEST_PASSWORD)

        url = reverse("surveys:take", kwargs={"slug": published_survey.slug})

        # Save empty draft
        response = client.post(
            url,
            {"action": "save_draft"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Should create progress with zero answers
        progress = SurveyProgress.objects.get(
            survey=published_survey, user=participant
        )
        assert progress.answered_count == 0
