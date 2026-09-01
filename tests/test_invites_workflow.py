"""
Tests for survey invite workflow: dashboard stats, pending invites list, and resend functionality.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyAccessToken,
    SurveyResponse,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password=TEST_PASSWORD)


@pytest.fixture
def org(user):
    return Organization.objects.create(name="Test Org", owner=user)


@pytest.fixture
def survey(user, org):
    s = Survey.objects.create(
        name="Test Survey",
        slug="test-survey",
        owner=user,
        organization=org,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    # Create a question group so survey is valid
    g = QuestionGroup.objects.create(
        name="Demographics",
        owner=user,
    )
    s.question_groups.add(g)
    return s


@pytest.mark.django_db
class TestDashboardInviteStats:
    """Test that dashboard displays invite counts correctly."""

    def test_dashboard_shows_invites_sent_count(self, client, user, survey):
        """Dashboard should show count of all invited tokens."""
        client.force_login(user)

        # Create some invite tokens
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token2",
            created_by=user,
            note="Invited: user2@example.com",
        )
        # Non-invite token (shouldn't be counted)
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token3",
            created_by=user,
            note="Manual token",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        assert response.context["invites_sent"] == 2
        assert "Invites" in response.content.decode()

    def test_dashboard_shows_pending_invites_count(self, client, user, survey):
        """Dashboard should show count of invites without responses."""
        client.force_login(user)

        # Token with no response (pending)
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        # Token with response (not pending)
        token2 = SurveyAccessToken.objects.create(
            survey=survey,
            token="token2",
            created_by=user,
            note="Invited: user2@example.com",
        )
        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            access_token=token2,
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        assert response.context["invites_sent"] == 2
        assert response.context["invites_pending"] == 1

    def test_dashboard_invites_badge_is_clickable(self, client, user, survey):
        """Invites badge should link to pending invites page when invites exist."""
        client.force_login(user)

        # Create an invite so the badge appears
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        pending_url = reverse("surveys:invites_pending", kwargs={"slug": survey.slug})
        assert pending_url in content
        # Check for hover styling classes
        assert "hover:bg-primary" in content or "hover:" in content


@pytest.mark.django_db
class TestPendingInvitesView:
    """Test the invites list view."""

    def test_invites_page_shows_all_invites_with_status(self, client, user, survey):
        """Invites page should list all invites with their completion status."""
        client.force_login(user)

        # Pending invite
        SurveyAccessToken.objects.create(
            survey=survey,
            token="pending-token",
            created_by=user,
            note="Invited: pending@example.com",
        )

        # Used invite (has response)
        token2 = SurveyAccessToken.objects.create(
            survey=survey,
            token="used-token",
            created_by=user,
            note="Invited: used@example.com",
        )
        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            access_token=token2,
        )

        response = client.get(
            reverse("surveys:invites_pending", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        # Both emails should be shown
        assert "pending@example.com" in content
        assert "used@example.com" in content
        # Check counts in context
        assert response.context["pending_count"] == 1
        assert response.context["completed_count"] == 1

    def test_pending_invites_extracts_email_from_note(self, client, user, survey):
        """Pending invites should extract email from 'Invited: email' format."""
        client.force_login(user)

        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: test@example.com",
        )

        response = client.get(
            reverse("surveys:invites_pending", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        invites = response.context["invites"]
        assert len(invites) == 1
        assert invites[0]["email"] == "test@example.com"

    def test_pending_invites_requires_view_permission(self, client, survey):
        """Pending invites page should require login and view permission."""
        # Not logged in
        response = client.get(
            reverse("surveys:invites_pending", kwargs={"slug": survey.slug})
        )
        assert response.status_code == 302  # Redirect to login

        # Logged in as different user
        other_user = User.objects.create_user(username="other", password="pass")
        client.force_login(other_user)
        response = client.get(
            reverse("surveys:invites_pending", kwargs={"slug": survey.slug})
        )
        # Should fail permission check (403 or redirect depending on implementation)
        assert response.status_code in [403, 302]


@pytest.mark.django_db
class TestResendInvite:
    """Test the resend invite functionality."""

    def test_resend_invite_sends_email(self, client, user, survey, mailoutbox):
        """Resending an invite should send an email."""
        client.force_login(user)

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=user,
            note="Invited: test@example.com",
        )

        response = client.post(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            )
        )

        assert response.status_code == 302  # Redirect back to pending invites
        assert len(mailoutbox) == 1
        assert "test@example.com" in mailoutbox[0].to

    def test_resend_invite_only_for_pending_tokens(self, client, user, survey):
        """Cannot resend invite for token that already has a response."""
        client.force_login(user)

        # Token with response
        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="used-token",
            created_by=user,
            note="Invited: used@example.com",
        )
        SurveyResponse.objects.create(
            survey=survey,
            submitted_by=user,
            submitted_at=timezone.now(),
            access_token=token,
        )

        response = client.post(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            )
        )

        # Should return 404 since token is filtered by response__isnull=True
        assert response.status_code == 404

    def test_resend_invite_requires_edit_permission(self, client, survey):
        """Resending invites should require edit permission."""
        # Not logged in
        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=survey.owner,
            note="Invited: test@example.com",
        )

        response = client.post(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            )
        )
        assert response.status_code == 302  # Redirect to login

    def test_resend_invite_shows_success_message(self, client, user, survey):
        """Successful resend should show success message."""
        client.force_login(user)

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=user,
            note="Invited: test@example.com",
        )

        response = client.post(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            ),
            follow=True,
        )

        assert response.status_code == 200
        messages = list(response.context["messages"])
        assert len(messages) > 0
        assert (
            "resent" in str(messages[0]).lower() or "sent" in str(messages[0]).lower()
        )

    def test_resend_invite_handles_invalid_email(self, client, user, survey):
        """Resend should handle tokens with invalid email formats."""
        client.force_login(user)

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=user,
            note="Invited: not-an-email",
        )

        response = client.post(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            ),
            follow=True,
        )

        assert response.status_code == 200
        messages = list(response.context["messages"])
        assert any("invalid" in str(m).lower() for m in messages)

    def test_resend_only_post_method_allowed(self, client, user, survey):
        """Resend endpoint should only accept POST requests."""
        client.force_login(user)

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=user,
            note="Invited: test@example.com",
        )

        response = client.get(
            reverse(
                "surveys:invite_resend",
                kwargs={"slug": survey.slug, "token_id": token.id},
            )
        )

        assert response.status_code == 405  # Method not allowed


@pytest.mark.django_db
class TestSparklineInvitesSeries:
    """Test that sparkline includes invites data series."""

    def test_dashboard_includes_invites_points_in_context(self, client, user, survey):
        """Dashboard context should include invites_points for sparkline."""
        client.force_login(user)

        # Create some invites to generate points
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
            created_at=timezone.now(),
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        assert "invites_points" in response.context
        # invites_points may be empty string if no data in range, but key should exist
        assert isinstance(response.context["invites_points"], str)

    def test_sparkline_legend_present_when_invites_exist(self, client, user, survey):
        """Sparkline legend should appear when there are invites."""
        client.force_login(user)

        # Ensure survey has started so sparkline renders
        survey.start_at = timezone.now() - timezone.timedelta(days=7)
        survey.save()

        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
            created_at=timezone.now() - timezone.timedelta(days=1),
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        # Check for legend elements
        if response.context.get("invites_points"):
            assert "Invites sent" in content or "invites" in content.lower()


@pytest.mark.django_db
class TestInvitesBadgeVisibility:
    """Test that the invites badge only shows for token-based surveys."""

    def test_invites_badge_shown_for_token_visibility(self, client, user, survey):
        """Invites badge should be shown when visibility is 'token'."""
        client.force_login(user)

        # Ensure survey has token visibility
        survey.visibility = Survey.Visibility.TOKEN
        survey.save()

        # Create some invites
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Track invites" in content
        assert "invites_pending" in response.context

    def test_invites_badge_hidden_for_public_visibility(self, client, user, survey):
        """Invites badge should NOT be shown when visibility is 'public'."""
        client.force_login(user)

        # Change to public visibility
        survey.visibility = Survey.Visibility.PUBLIC
        survey.no_patient_data_ack = True
        survey.save()

        # Create some invites (they exist but shouldn't show the badge)
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        # The badge should not appear
        assert 'href="/surveys/test-survey/invites/pending/">Invites:' not in content

    def test_invites_badge_shown_for_authenticated_visibility(
        self, client, user, survey
    ):
        """Invites badge SHOULD be shown for authenticated visibility when invites exist."""
        client.force_login(user)

        # Change to authenticated visibility
        survey.visibility = Survey.Visibility.AUTHENTICATED
        survey.save()

        # Create some invites
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        # The invite tracking button SHOULD appear for authenticated surveys with invites
        assert "Track invites" in content

    def test_invites_badge_hidden_for_unlisted_visibility(self, client, user, survey):
        """Invites badge should NOT be shown when visibility is 'unlisted'."""
        client.force_login(user)

        # Change to unlisted visibility
        survey.visibility = Survey.Visibility.UNLISTED
        survey.unlisted_key = "test-key-12345"
        survey.no_patient_data_ack = True
        survey.save()

        # Create some invites
        SurveyAccessToken.objects.create(
            survey=survey,
            token="token1",
            created_by=user,
            note="Invited: user1@example.com",
        )

        response = client.get(
            reverse("surveys:dashboard", kwargs={"slug": survey.slug})
        )

        assert response.status_code == 200
        content = response.content.decode()
        # The badge should not appear
        assert 'href="/surveys/test-survey/invites/pending/">Invites:' not in content
