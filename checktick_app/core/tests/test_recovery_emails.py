"""
Tests for key recovery email notifications.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_email_backend():
    """Mock Django email backend."""
    with patch("checktick_app.core.email_utils.EmailMultiAlternatives") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        mock_instance.send.return_value = 1
        yield mock


@pytest.fixture
def mock_branding():
    """Mock platform branding."""
    with patch("checktick_app.core.email_utils.get_platform_branding") as mock:
        mock.return_value = {
            "title": "CheckTick Test",
            "primary_color": "#3b82f6",
            "font_heading": "Arial",
            "font_body": "Arial",
        }
        yield mock


class TestRecoveryRequestSubmittedEmail:
    """Tests for send_recovery_request_submitted_email."""

    def test_sends_email_with_correct_subject(self, mock_email_backend, mock_branding):
        """Test email is sent with correct subject."""
        from checktick_app.core.email_utils import send_recovery_request_submitted_email

        result = send_recovery_request_submitted_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678-1234-1234-1234-123456789012",
            survey_name="Health Survey",
            reason="Forgot passphrase",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "Key Recovery Request Submitted" in call_kwargs[1]["subject"]
        assert "REC-1234" in call_kwargs[1]["subject"]

    def test_includes_request_details_in_content(
        self, mock_email_backend, mock_branding
    ):
        """Test email content includes request details."""
        from checktick_app.core.email_utils import send_recovery_request_submitted_email

        send_recovery_request_submitted_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            reason="Forgot passphrase",
            estimated_review_time="24-48 hours",
        )

        mock_email_backend.assert_called_once()
        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        # Content comes from template, check key elements
        assert "Test User" in body or "user_name" in body.lower()


class TestRecoveryAdminNotificationEmail:
    """Tests for send_recovery_admin_notification_email."""

    def test_sends_email_to_admin(self, mock_email_backend, mock_branding):
        """Test email is sent to admin."""
        from checktick_app.core.email_utils import (
            send_recovery_admin_notification_email,
        )

        result = send_recovery_admin_notification_email(
            to_email="admin@example.com",
            admin_name="Admin User",
            request_id="REC-12345678",
            requester_name="Test User",
            requester_email="user@example.com",
            survey_name="Health Survey",
            reason="Forgot passphrase",
            dashboard_url="https://example.com/admin/recovery/REC-12345678",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "admin@example.com" in call_kwargs[1]["to"]
        assert "⚠️" in call_kwargs[1]["subject"]
        assert "Pending Review" in call_kwargs[1]["subject"]

    def test_includes_dashboard_url(self, mock_email_backend, mock_branding):
        """Test email includes dashboard URL."""
        from checktick_app.core.email_utils import (
            send_recovery_admin_notification_email,
        )

        send_recovery_admin_notification_email(
            to_email="admin@example.com",
            admin_name="Admin User",
            request_id="REC-12345678",
            requester_name="Test User",
            requester_email="user@example.com",
            survey_name="Health Survey",
            reason="Forgot passphrase",
            dashboard_url="https://example.com/admin/recovery/REC-12345678",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "https://example.com/admin/recovery/REC-12345678" in body


class TestRecoveryVerificationNeededEmail:
    """Tests for send_recovery_verification_needed_email."""

    def test_sends_verification_email(self, mock_email_backend, mock_branding):
        """Test verification email is sent."""
        from checktick_app.core.email_utils import (
            send_recovery_verification_needed_email,
        )

        result = send_recovery_verification_needed_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            verification_method="Email Verification",
            verification_instructions="Click the link sent to your registered email.",
            expires_at="2024-01-15 14:00:00 UTC",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "Identity Verification Required" in call_kwargs[1]["subject"]

    def test_includes_expiration_time(self, mock_email_backend, mock_branding):
        """Test email includes expiration time."""
        from checktick_app.core.email_utils import (
            send_recovery_verification_needed_email,
        )

        send_recovery_verification_needed_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            verification_method="Email Verification",
            verification_instructions="Click the link.",
            expires_at="2024-01-15 14:00:00 UTC",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "2024-01-15 14:00:00 UTC" in body


class TestRecoveryApprovedEmail:
    """Tests for send_recovery_approved_email."""

    def test_sends_approval_email(self, mock_email_backend, mock_branding):
        """Test approval email is sent."""
        from checktick_app.core.email_utils import send_recovery_approved_email

        result = send_recovery_approved_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            time_delay_hours=24,
            access_available_at="2024-01-16 14:00:00 UTC",
            approved_by="Admin User",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "✅" in call_kwargs[1]["subject"]
        assert "Approved" in call_kwargs[1]["subject"]

    def test_includes_time_delay(self, mock_email_backend, mock_branding):
        """Test email includes time delay information."""
        from checktick_app.core.email_utils import send_recovery_approved_email

        send_recovery_approved_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            time_delay_hours=24,
            access_available_at="2024-01-16 14:00:00 UTC",
            approved_by="Admin User",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "24" in body  # Time delay hours
        assert "2024-01-16 14:00:00 UTC" in body


class TestRecoveryReadyEmail:
    """Tests for send_recovery_ready_email."""

    def test_sends_ready_email(self, mock_email_backend, mock_branding):
        """Test ready email is sent."""
        from checktick_app.core.email_utils import send_recovery_ready_email

        result = send_recovery_ready_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            recovery_url="https://example.com/recovery/complete/REC-12345678",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "🔑" in call_kwargs[1]["subject"]
        assert "Ready" in call_kwargs[1]["subject"]

    def test_includes_recovery_url(self, mock_email_backend, mock_branding):
        """Test email includes recovery URL."""
        from checktick_app.core.email_utils import send_recovery_ready_email

        send_recovery_ready_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            recovery_url="https://example.com/recovery/complete/REC-12345678",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "https://example.com/recovery/complete/REC-12345678" in body


class TestRecoveryRejectedEmail:
    """Tests for send_recovery_rejected_email."""

    def test_sends_rejection_email(self, mock_email_backend, mock_branding):
        """Test rejection email is sent."""
        from checktick_app.core.email_utils import send_recovery_rejected_email

        result = send_recovery_rejected_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            reason="Identity could not be verified",
            rejected_by="Admin User",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "❌" in call_kwargs[1]["subject"]
        assert "Rejected" in call_kwargs[1]["subject"]

    def test_includes_rejection_reason(self, mock_email_backend, mock_branding):
        """Test email includes rejection reason."""
        from checktick_app.core.email_utils import send_recovery_rejected_email

        send_recovery_rejected_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            reason="Identity could not be verified",
            rejected_by="Admin User",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "Identity could not be verified" in body


class TestRecoveryCancelledEmail:
    """Tests for send_recovery_cancelled_email."""

    def test_sends_cancellation_email(self, mock_email_backend, mock_branding):
        """Test cancellation email is sent."""
        from checktick_app.core.email_utils import send_recovery_cancelled_email

        result = send_recovery_cancelled_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            cancelled_by="User Request",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "Cancelled" in call_kwargs[1]["subject"]

    def test_includes_optional_reason(self, mock_email_backend, mock_branding):
        """Test email includes optional cancellation reason."""
        from checktick_app.core.email_utils import send_recovery_cancelled_email

        send_recovery_cancelled_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            cancelled_by="Admin User",
            reason="Duplicate request",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "Duplicate request" in body


class TestRecoverySecurityAlertEmail:
    """Tests for send_recovery_security_alert_email."""

    def test_sends_security_alert(self, mock_email_backend, mock_branding):
        """Test security alert email is sent."""
        from checktick_app.core.email_utils import send_recovery_security_alert_email

        result = send_recovery_security_alert_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            alert_type="Unusual Location",
            alert_details="Recovery request initiated from a new location.",
            action_url="https://example.com/security/report",
        )

        assert result is True
        mock_email_backend.assert_called_once()
        call_kwargs = mock_email_backend.call_args
        assert "🚨" in call_kwargs[1]["subject"]
        assert "Security Alert" in call_kwargs[1]["subject"]

    def test_includes_action_url(self, mock_email_backend, mock_branding):
        """Test email includes action URL."""
        from checktick_app.core.email_utils import send_recovery_security_alert_email

        send_recovery_security_alert_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            alert_type="Unusual Location",
            alert_details="Recovery request initiated from a new location.",
            action_url="https://example.com/security/report",
        )

        call_args = mock_email_backend.call_args
        body = call_args[1]["body"]
        assert "https://example.com/security/report" in body
        assert "Unusual Location" in body


class TestEmailTemplateRendering:
    """Tests for email template rendering."""

    def test_template_renders_with_context(self, mock_email_backend, mock_branding):
        """Test that templates render correctly with context."""
        from checktick_app.core.email_utils import send_recovery_request_submitted_email

        # This test uses the actual templates
        result = send_recovery_request_submitted_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Health Survey",
            reason="Forgot passphrase",
        )

        assert result is True


class TestEmailFailureHandling:
    """Tests for email failure handling."""

    def test_returns_false_on_send_failure(self, mock_branding):
        """Test that False is returned when email send fails."""
        from checktick_app.core.email_utils import send_recovery_request_submitted_email

        with patch("checktick_app.core.email_utils.EmailMultiAlternatives") as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            mock_instance.send.side_effect = Exception("SMTP Error")

            result = send_recovery_request_submitted_email(
                to_email="user@example.com",
                user_name="Test User",
                request_id="REC-12345678",
                survey_name="Health Survey",
                reason="Forgot passphrase",
            )

            assert result is False


class TestFallbackContent:
    """Tests for fallback content when templates don't exist."""

    def test_all_email_functions_have_fallback_content(
        self, mock_email_backend, mock_branding
    ):
        """Test all recovery email functions can send emails (have fallback or templates)."""
        from checktick_app.core.email_utils import (
            send_recovery_admin_notification_email,
            send_recovery_approved_email,
            send_recovery_cancelled_email,
            send_recovery_ready_email,
            send_recovery_rejected_email,
            send_recovery_request_submitted_email,
            send_recovery_security_alert_email,
            send_recovery_verification_needed_email,
        )

        # All these should succeed with templates available
        assert send_recovery_request_submitted_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            reason="Test reason",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_admin_notification_email(
            to_email="admin@example.com",
            admin_name="Admin",
            request_id="REC-12345678",
            requester_name="Test User",
            requester_email="user@example.com",
            survey_name="Test Survey",
            reason="Test reason",
            dashboard_url="https://example.com/dashboard",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_verification_needed_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            verification_method="Email",
            verification_instructions="Click the link",
            expires_at="2024-01-15",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_approved_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            time_delay_hours=24,
            access_available_at="2024-01-16",
            approved_by="Admin",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_ready_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            recovery_url="https://example.com/recover",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_rejected_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            reason="Identity not verified",
            rejected_by="Admin",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_cancelled_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            cancelled_by="User",
        )

        mock_email_backend.reset_mock()
        assert send_recovery_security_alert_email(
            to_email="user@example.com",
            user_name="Test User",
            request_id="REC-12345678",
            survey_name="Test Survey",
            alert_type="Unusual activity",
            alert_details="Request from new location",
            action_url="https://example.com/report",
        )
