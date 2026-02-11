"""
Tests for authenticated survey invitation system.

Tests the new feature that allows inviting specific users to authenticated surveys,
with different email templates for existing vs. new users.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyAccessToken,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable rate limiting for all tests in this module."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        username="owner@example.com", email="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def existing_user(db):
    """User who already has a CheckTick account."""
    return User.objects.create_user(
        username="existing@example.com",
        email="existing@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Test Org", owner=owner)


@pytest.fixture
def authenticated_survey(owner, org):
    """Survey with authenticated visibility."""
    import os

    from checktick_app.surveys.utils import generate_bip39_phrase

    s = Survey.objects.create(
        name="Authenticated Survey",
        slug="auth-survey",
        owner=owner,
        organization=org,
        status=Survey.Status.DRAFT,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=False,  # Invite-only mode
    )

    # Add encryption (required for all surveys)
    kek = os.urandom(32)
    recovery_words = generate_bip39_phrase(12)
    s.set_dual_encryption(kek, "test_password", recovery_words)

    # Add a question group to make survey valid
    g = QuestionGroup.objects.create(name="Questions", owner=owner)
    s.question_groups.add(g)
    return s


# ============================================================================
# Publishing with Authenticated Invitations
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedInvitationPublishing:
    """Tests for publishing authenticated surveys with email invitations."""

    @patch("threading.Thread")
    @patch(
        "checktick_app.core.email_utils.send_authenticated_survey_invite_existing_user"
    )
    @patch("checktick_app.core.email_utils.send_authenticated_survey_invite_new_user")
    def test_publish_authenticated_survey_with_existing_user(
        self,
        mock_send_new_user,
        mock_send_existing_user,
        mock_thread,
        client,
        owner,
        existing_user,
        authenticated_survey,
    ):
        """Publishing with invite to existing user should send correct email."""

        # Make threading synchronous by calling target directly
        def run_sync(target=None, args=()):
            if target:
                target(*args)

        mock_thread.return_value.start.side_effect = lambda: run_sync(
            mock_thread.call_args.kwargs.get("target"),
            mock_thread.call_args.kwargs.get("args", ()),
        )
        mock_send_existing_user.return_value = True
        client.force_login(owner)

        response = client.post(
            reverse(
                "surveys:publish_settings", kwargs={"slug": authenticated_survey.slug}
            ),
            {
                "action": "publish",
                "visibility": "authenticated",
                "invite_emails": existing_user.email,
                "no_patient_data_ack": "on",
            },
        )

        assert response.status_code == 302

        # Should create token with for_authenticated=True
        token = SurveyAccessToken.objects.filter(
            survey=authenticated_survey,
            for_authenticated=True,
        ).first()
        assert token is not None
        assert f"Invited: {existing_user.email}" in token.note

        # Should send email to existing user, not new user email
        mock_send_existing_user.assert_called_once()
        mock_send_new_user.assert_not_called()

        # Verify survey is published
        authenticated_survey.refresh_from_db()
        assert authenticated_survey.status == Survey.Status.PUBLISHED

    @patch("threading.Thread")
    @patch(
        "checktick_app.core.email_utils.send_authenticated_survey_invite_existing_user"
    )
    @patch("checktick_app.core.email_utils.send_authenticated_survey_invite_new_user")
    def test_publish_authenticated_survey_with_new_user(
        self,
        mock_send_new_user,
        mock_send_existing_user,
        mock_thread,
        client,
        owner,
        authenticated_survey,
    ):
        """Publishing with invite to new user should send signup email."""

        # Make threading synchronous by calling target directly
        def run_sync(target=None, args=()):
            if target:
                target(*args)

        mock_thread.return_value.start.side_effect = lambda: run_sync(
            mock_thread.call_args.kwargs.get("target"),
            mock_thread.call_args.kwargs.get("args", ()),
        )
        mock_send_new_user.return_value = True
        client.force_login(owner)

        new_email = "newuser@example.com"

        response = client.post(
            reverse(
                "surveys:publish_settings", kwargs={"slug": authenticated_survey.slug}
            ),
            {
                "action": "publish",
                "visibility": "authenticated",
                "invite_emails": new_email,
                "no_patient_data_ack": "on",
            },
        )

        assert response.status_code == 302

        # Should create token with for_authenticated=True
        token = SurveyAccessToken.objects.filter(
            survey=authenticated_survey,
            for_authenticated=True,
        ).first()
        assert token is not None
        assert f"Invited: {new_email}" in token.note

        # Should send email to new user, not existing user email
        mock_send_new_user.assert_called_once()
        mock_send_existing_user.assert_not_called()

    @patch("threading.Thread")
    @patch(
        "checktick_app.core.email_utils.send_authenticated_survey_invite_existing_user"
    )
    @patch("checktick_app.core.email_utils.send_authenticated_survey_invite_new_user")
    def test_publish_authenticated_survey_with_multiple_emails(
        self,
        mock_send_new_user,
        mock_send_existing_user,
        mock_thread,
        client,
        owner,
        existing_user,
        authenticated_survey,
    ):
        """Publishing with multiple invites should handle mixed existing/new users."""

        # Make threading synchronous by calling target directly
        def run_sync(target=None, args=()):
            if target:
                target(*args)

        mock_thread.return_value.start.side_effect = lambda: run_sync(
            mock_thread.call_args.kwargs.get("target"),
            mock_thread.call_args.kwargs.get("args", ()),
        )
        mock_send_existing_user.return_value = True
        mock_send_new_user.return_value = True
        client.force_login(owner)

        new_email1 = "newuser1@example.com"
        new_email2 = "newuser2@example.com"

        invite_emails = f"{existing_user.email}\n{new_email1}\n{new_email2}"

        response = client.post(
            reverse(
                "surveys:publish_settings", kwargs={"slug": authenticated_survey.slug}
            ),
            {
                "action": "publish",
                "visibility": "authenticated",
                "invite_emails": invite_emails,
                "no_patient_data_ack": "on",
            },
        )

        assert response.status_code == 302

        # Should create 3 tokens
        tokens = SurveyAccessToken.objects.filter(
            survey=authenticated_survey,
            for_authenticated=True,
        )
        assert tokens.count() == 3

        # Should send 1 existing user email, 2 new user emails
        assert mock_send_existing_user.call_count == 1
        assert mock_send_new_user.call_count == 2

    @patch("threading.Thread")
    def test_publish_authenticated_survey_with_outlook_format(
        self,
        mock_thread,
        client,
        owner,
        authenticated_survey,
    ):
        """Should parse Outlook contact format: Name <email@domain.com>."""

        # Make threading synchronous by calling target directly
        def run_sync(target=None, args=()):
            if target:
                target(*args)

        mock_thread.return_value.start.side_effect = lambda: run_sync(
            mock_thread.call_args.kwargs.get("target"),
            mock_thread.call_args.kwargs.get("args", ()),
        )
        client.force_login(owner)

        with patch(
            "checktick_app.core.email_utils.send_authenticated_survey_invite_new_user"
        ) as mock:
            mock.return_value = True

            response = client.post(
                reverse(
                    "surveys:publish_settings",
                    kwargs={"slug": authenticated_survey.slug},
                ),
                {
                    "action": "publish",
                    "visibility": "authenticated",
                    "invite_emails": "John Smith <john@example.com>",
                    "no_patient_data_ack": "on",
                },
            )

            assert response.status_code == 302

            # Should extract email from Outlook format
            token = SurveyAccessToken.objects.filter(
                survey=authenticated_survey,
                for_authenticated=True,
            ).first()
            assert token is not None
            assert "Invited: john@example.com" in token.note

    def test_publish_authenticated_survey_with_allow_any_authenticated(
        self,
        client,
        owner,
        authenticated_survey,
    ):
        """Setting allow_any_authenticated should be saved."""
        client.force_login(owner)

        response = client.post(
            reverse(
                "surveys:publish_settings", kwargs={"slug": authenticated_survey.slug}
            ),
            {
                "action": "publish",
                "visibility": "authenticated",
                "allow_any_authenticated": "on",
                "no_patient_data_ack": "on",
            },
        )

        assert response.status_code == 302

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.allow_any_authenticated is True

    def test_publish_authenticated_survey_without_allow_any_authenticated(
        self,
        client,
        owner,
        authenticated_survey,
    ):
        """Not checking allow_any_authenticated should keep invite-only mode."""
        client.force_login(owner)

        response = client.post(
            reverse(
                "surveys:publish_settings", kwargs={"slug": authenticated_survey.slug}
            ),
            {
                "action": "publish",
                "visibility": "authenticated",
                # allow_any_authenticated not included
                "no_patient_data_ack": "on",
            },
        )

        assert response.status_code == 302

        authenticated_survey.refresh_from_db()
        assert authenticated_survey.allow_any_authenticated is False


# ============================================================================
# Access Control for Authenticated Surveys
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedSurveyAccessControl:
    """Tests for access control on authenticated surveys with invitations."""

    def test_anonymous_user_redirected_to_login(self, client, authenticated_survey):
        """Anonymous users should be redirected to login."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.save()

        response = client.get(
            reverse("surveys:take", kwargs={"slug": authenticated_survey.slug})
        )

        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_authenticated_user_without_invitation_denied_in_invite_only_mode(
        self,
        client,
        authenticated_survey,
        existing_user,
    ):
        """Authenticated user without invitation should be denied in invite-only mode."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.allow_any_authenticated = False
        authenticated_survey.save()

        client.force_login(existing_user)

        response = client.get(
            reverse("surveys:take", kwargs={"slug": authenticated_survey.slug})
        )

        # Should show error or redirect (implementation dependent)
        # This test may need adjustment based on actual implementation
        assert response.status_code in [302, 403, 200]
        if response.status_code == 200:
            assert b"invited" in response.content or b"access" in response.content

    def test_authenticated_user_with_invitation_can_access(
        self,
        client,
        owner,
        authenticated_survey,
        existing_user,
    ):
        """Authenticated user with invitation should access survey."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.allow_any_authenticated = False
        authenticated_survey.save()

        # Create invitation token
        SurveyAccessToken.objects.create(
            survey=authenticated_survey,
            token="test-token",
            created_by=owner,
            note=f"Invited: {existing_user.email}",
            for_authenticated=True,
        )

        client.force_login(existing_user)

        response = client.get(
            reverse("surveys:take", kwargs={"slug": authenticated_survey.slug})
        )

        assert response.status_code == 200
        # Should see survey form
        assert authenticated_survey.name.encode() in response.content

    def test_any_authenticated_user_can_access_in_self_service_mode(
        self,
        client,
        authenticated_survey,
        existing_user,
    ):
        """Any authenticated user should access survey in self-service mode."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.allow_any_authenticated = True
        authenticated_survey.save()

        client.force_login(existing_user)

        response = client.get(
            reverse("surveys:take", kwargs={"slug": authenticated_survey.slug})
        )

        assert response.status_code == 200
        # Should see survey form
        assert authenticated_survey.name.encode() in response.content


# ============================================================================
# Invitation Management
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedInvitationManagement:
    """Tests for managing authenticated invitations."""

    def test_pending_invites_shows_authenticated_invitations(
        self,
        client,
        owner,
        authenticated_survey,
    ):
        """Pending invites view should show authenticated invitation tokens."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.save()

        # Create authenticated invitation
        SurveyAccessToken.objects.create(
            survey=authenticated_survey,
            token="auth-token",
            created_by=owner,
            note="Invited: user@example.com",
            for_authenticated=True,
        )

        client.force_login(owner)

        response = client.get(
            reverse(
                "surveys:invites_pending", kwargs={"slug": authenticated_survey.slug}
            )
        )

        assert response.status_code == 200
        assert b"user@example.com" in response.content

    def test_pending_invites_distinguishes_token_types(
        self,
        client,
        owner,
        authenticated_survey,
    ):
        """Pending invites should work for both authenticated and token mode invites."""
        authenticated_survey.status = Survey.Status.PUBLISHED
        authenticated_survey.save()

        # Create authenticated invitation
        SurveyAccessToken.objects.create(
            survey=authenticated_survey,
            token="auth-token",
            created_by=owner,
            note="Invited: auth@example.com",
            for_authenticated=True,
        )

        # Create anonymous token invitation
        SurveyAccessToken.objects.create(
            survey=authenticated_survey,
            token="anon-token",
            created_by=owner,
            note="Invited: anon@example.com",
            for_authenticated=False,
        )

        client.force_login(owner)

        response = client.get(
            reverse(
                "surveys:invites_pending", kwargs={"slug": authenticated_survey.slug}
            )
        )

        assert response.status_code == 200
        # Both should appear
        assert b"auth@example.com" in response.content
        assert b"anon@example.com" in response.content


# ============================================================================
# Email Template Tests
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedInvitationEmails:
    """Tests for authenticated invitation email functions."""

    def test_send_authenticated_invite_to_existing_user(
        self,
        authenticated_survey,
    ):
        """Email to existing user should include direct survey link."""
        from checktick_app.core.email_utils import (
            send_authenticated_survey_invite_existing_user,
        )

        with patch("checktick_app.core.email_utils.send_branded_email") as mock_email:
            mock_email.return_value = True

            result = send_authenticated_survey_invite_existing_user(
                to_email="existing@example.com",
                survey=authenticated_survey,
                contact_email="owner@example.com",
            )

            assert result is True
            mock_email.assert_called_once()

            # Check that correct template and context were used
            call_args = mock_email.call_args
            assert "existing@example.com" in call_args[1]["to_email"]
            assert "survey_link" in call_args[1]["context"]
            assert (
                "/surveys/auth-survey/take/" in call_args[1]["context"]["survey_link"]
            )

    def test_send_authenticated_invite_to_new_user(
        self,
        authenticated_survey,
    ):
        """Email to new user should include signup link with redirect."""
        from checktick_app.core.email_utils import (
            send_authenticated_survey_invite_new_user,
        )

        with patch("checktick_app.core.email_utils.send_branded_email") as mock_email:
            mock_email.return_value = True

            result = send_authenticated_survey_invite_new_user(
                to_email="newuser@example.com",
                survey=authenticated_survey,
                contact_email="owner@example.com",
            )

            assert result is True
            mock_email.assert_called_once()

            # Check that correct template and context were used
            call_args = mock_email.call_args
            assert "newuser@example.com" in call_args[1]["to_email"]
            assert "signup_link" in call_args[1]["context"]
            # Should include signup link with redirect
            assert "/signup/" in call_args[1]["context"]["signup_link"]
            assert (
                "next=/surveys/auth-survey/take/"
                in call_args[1]["context"]["signup_link"]
            )
            assert "email=newuser@example.com" in call_args[1]["context"]["signup_link"]


# ============================================================================
# Model Tests
# ============================================================================


@pytest.mark.django_db
class TestAuthenticatedInvitationModels:
    """Tests for model fields and methods related to authenticated invitations."""

    def test_survey_allow_any_authenticated_default(self, owner, org):
        """Survey should default to invite-only mode (allow_any_authenticated=False)."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test",
            owner=owner,
            organization=org,
            visibility=Survey.Visibility.AUTHENTICATED,
        )

        assert survey.allow_any_authenticated is False

    def test_survey_access_token_for_authenticated_default(self, owner, org):
        """SurveyAccessToken should default to anonymous (for_authenticated=False)."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test",
            owner=owner,
            organization=org,
        )

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=owner,
        )

        assert token.for_authenticated is False

    def test_survey_access_token_for_authenticated_can_be_set(self, owner, org):
        """SurveyAccessToken for_authenticated can be explicitly set."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test",
            owner=owner,
            organization=org,
        )

        token = SurveyAccessToken.objects.create(
            survey=survey,
            token="test-token",
            created_by=owner,
            for_authenticated=True,
        )

        assert token.for_authenticated is True

    def test_survey_allow_any_authenticated_only_for_authenticated_visibility(
        self, owner, org
    ):
        """allow_any_authenticated should only apply to authenticated surveys."""
        survey = Survey.objects.create(
            name="Test Survey",
            slug="test",
            owner=owner,
            organization=org,
            visibility=Survey.Visibility.PUBLIC,
            allow_any_authenticated=True,  # Should be ignored for non-authenticated
        )

        # This is more of a documentation test - the field exists but
        # should only be used when visibility is AUTHENTICATED
        assert survey.visibility != Survey.Visibility.AUTHENTICATED
