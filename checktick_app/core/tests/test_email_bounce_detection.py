"""Tests for email bounce detection functionality."""

from smtplib import SMTPRecipientsRefused
from socket import gaierror
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = "testpass123"


class TestEmailBounceDetection(TestCase):
    """Test email bounce detection during signup."""

    def setUp(self):
        self.client = Client()

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_signup_with_smtp_recipients_refused_deletes_account(self, mock_send_mail):
        """Test that SMTPRecipientsRefused errors result in account deletion."""
        # Mock an SMTP recipient refused error
        mock_send_mail.side_effect = SMTPRecipientsRefused(
            {"invalid@example.com": (550, "Recipient address rejected: User unknown")}
        )

        # Attempt signup with invalid email
        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "invalid@example.com",
                "email_confirm": "invalid@example.com",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect back to signup page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:signup"))

        # Check that user account was not created (deleted due to bounce)
        self.assertFalse(User.objects.filter(email="invalid@example.com").exists())

        # Check that appropriate error message is shown
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "We apologise that it has not been possible to create an account",
            messages[0].message,
        )

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_signup_with_dns_error_deletes_account(self, mock_send_mail):
        """Test that DNS resolution errors result in account deletion."""
        # Mock a DNS resolution error
        mock_send_mail.side_effect = gaierror("Name or service not known")

        # Attempt signup with domain that doesn't exist
        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "user@nonexistentdomain.invalid",
                "email_confirm": "user@nonexistentdomain.invalid",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect back to signup page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:signup"))

        # Check that user account was not created (deleted due to bounce)
        self.assertFalse(
            User.objects.filter(email="user@nonexistentdomain.invalid").exists()
        )

        # Check that appropriate error message is shown
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn(
            "We apologise that it has not been possible to create an account",
            messages[0].message,
        )

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_signup_with_temporary_smtp_error_shows_warning(self, mock_send_mail):
        """Test that temporary SMTP errors show warning but don't delete account."""
        # Mock a temporary SMTP error (not recipient refused)
        mock_send_mail.side_effect = Exception("Temporary SMTP server issue")

        # Attempt signup
        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "temporary@example.com",
                "email_confirm": "temporary@example.com",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect to home (signup succeeded, but email failed)
        self.assertEqual(response.status_code, 302)

        # Check that user account was created
        self.assertTrue(User.objects.filter(email="temporary@example.com").exists())

        # Check that warning message is shown
        messages = list(response.wsgi_request._messages)
        warning_message = [m for m in messages if "trouble sending" in m.message][0]
        self.assertIn(
            "We had trouble sending a confirmation email", warning_message.message
        )

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_signup_with_valid_email_works_normally(self, mock_send_mail):
        """Test that signup with valid email works normally."""
        # Mock successful email sending (default behavior)
        mock_send_mail.return_value = None  # Successful send

        # Attempt signup with valid email
        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "valid@example.com",
                "email_confirm": "valid@example.com",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect to home
        self.assertEqual(response.status_code, 302)

        # Check that user account was created
        self.assertTrue(User.objects.filter(email="valid@example.com").exists())

        # Check that confirmation email was "sent"
        self.assertEqual(mock_send_mail.call_count, 1)

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_send_confirmation_email_returns_correct_tuple(self, mock_send_mail):
        """Test that send_confirmation_email returns the correct tuple format."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        # Create a test user
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )

        # Mock successful email sending
        mock_send_mail.return_value = None

        # Call the method
        result = EmailConfirmationManager.send_confirmation_email(user)
        confirmation, success, error_info = result

        # Check the return values
        self.assertIsNotNone(confirmation)
        self.assertTrue(success)
        self.assertIsNone(error_info)

        # Check that a token was created
        self.assertTrue(EmailConfirmationToken.objects.filter(user=user).exists())

    @patch("checktick_app.core.email_confirmation.send_mail")
    def test_send_confirmation_email_with_error_returns_correct_tuple(
        self, mock_send_mail
    ):
        """Test that send_confirmation_email returns the correct tuple format on error."""
        from checktick_app.core.email_confirmation import EmailConfirmationManager

        # Create a test user
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )

        # Mock an email sending error
        mock_send_mail.side_effect = Exception("Test error")

        # Call the method
        result = EmailConfirmationManager.send_confirmation_email(user)
        confirmation, success, error_info = result

        # Check the return values
        self.assertIsNotNone(confirmation)
        self.assertFalse(success)
        self.assertIsNotNone(error_info)
        self.assertIn("type", error_info)
        self.assertIn("message", error_info)
        self.assertEqual(error_info["message"], "Test error")
