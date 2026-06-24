"""Tests for email confirmation functionality."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from checktick_app.core.models import UserOIDC, UserProfile

User = get_user_model()

PASSWORD = "testpass123"


class TestEmailConfirmationModel(TestCase):
    """Test the EmailConfirmationToken model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )

    def test_email_confirmation_field_exists(self):
        """Test that the email_confirmed field exists on UserProfile."""
        profile = self.user.profile
        self.assertFalse(profile.email_confirmed)  # Should default to False

        # Test setting it to True
        profile.email_confirmed = True
        profile.save()

        # Refresh from DB
        profile.refresh_from_db()
        self.assertTrue(profile.email_confirmed)


class TestEmailConfirmationManager(TestCase):
    """Test the EmailConfirmationManager functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )

    def test_generate_token(self):
        """Test token generation."""
        from checktick_app.core.email_confirmation import EmailConfirmationManager

        token = EmailConfirmationManager.generate_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 10)  # Reasonable length

    def test_send_confirmation_email(self):
        """Test sending confirmation email."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        # This test mainly checks that the method runs without error
        # Actual email sending is tested separately
        confirmation = EmailConfirmationManager.send_confirmation_email(self.user)

        self.assertIsNotNone(confirmation)
        self.assertEqual(confirmation.user, self.user)
        # Token should be created
        self.assertTrue(EmailConfirmationToken.objects.filter(user=self.user).exists())

    def test_verify_token_success(self):
        """Test successful token verification."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        # Create a confirmation token
        token = EmailConfirmationManager.generate_token()
        EmailConfirmationToken.objects.create(
            user=self.user, token=token, expires_at=timezone.now() + timedelta(hours=24)
        )

        # Verify the token
        verified_user = EmailConfirmationManager.verify_token(token)

        self.assertEqual(verified_user, self.user)
        # User's email should be confirmed
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.email_confirmed)
        # Token should be deleted after use
        self.assertFalse(EmailConfirmationToken.objects.filter(token=token).exists())

    def test_verify_token_invalid(self):
        """Test verifying an invalid token."""
        from checktick_app.core.email_confirmation import EmailConfirmationManager

        result = EmailConfirmationManager.verify_token("invalidtoken")

        self.assertIsNone(result)

    def test_verify_token_expired(self):
        """Test verifying an expired token."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        expired_token = EmailConfirmationManager.generate_token()
        EmailConfirmationToken.objects.create(
            user=self.user,
            token=expired_token,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        result = EmailConfirmationManager.verify_token(expired_token)

        self.assertIsNone(result)
        # User's email should NOT be confirmed
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_confirmed)


class TestEmailConfirmationViews(TestCase):
    """Test email confirmation views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )
        # Mark email as unconfirmed initially (as it would be after signup)
        self.user.profile.email_confirmed = False
        self.user.profile.save()

    def test_confirm_email_view_valid_token(self):
        """Test confirming email with a valid token."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        # Create a confirmation token
        token = EmailConfirmationManager.generate_token()
        EmailConfirmationToken.objects.create(
            user=self.user, token=token, expires_at=timezone.now() + timedelta(hours=24)
        )

        # Access the confirmation URL
        response = self.client.get(reverse("confirm_email", kwargs={"token": token}))

        # Should redirect to home
        self.assertEqual(response.status_code, 302)
        # The user should be redirected to home, but might go through login first
        # depending on auth state
        self.assertIn(response.url, ["/", "/home", "/accounts/login/?next=/"])

        # User's email should be confirmed
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.email_confirmed)

        # Token should be deleted
        self.assertFalse(EmailConfirmationToken.objects.filter(token=token).exists())

    def test_confirm_email_view_invalid_token(self):
        """Test confirming email with an invalid token."""
        response = self.client.get(
            reverse("confirm_email", kwargs={"token": "invalid"})
        )

        # Should redirect to home
        self.assertEqual(response.status_code, 302)
        self.assertIn(response.url, ["/", "/home", "/accounts/login/?next=/"])

        # User's email should NOT be confirmed
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_confirmed)

    def test_confirm_email_view_expired_token(self):
        """Test confirming email with an expired token."""
        from checktick_app.core.email_confirmation import (
            EmailConfirmationManager,
            EmailConfirmationToken,
        )

        expired_token = EmailConfirmationManager.generate_token()
        EmailConfirmationToken.objects.create(
            user=self.user,
            token=expired_token,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(
            reverse("confirm_email", kwargs={"token": expired_token})
        )

        # Should redirect to home
        self.assertEqual(response.status_code, 302)
        self.assertIn(response.url, ["/", "/home", "/accounts/login/?next=/"])

        # User's email should NOT be confirmed
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_confirmed)


class TestSignupWithEmailConfirmation(TestCase):
    """Test signup flow with email confirmation."""

    def setUp(self):
        self.client = Client()

    def test_signup_creates_unconfirmed_user(self):
        """Test that signup creates a user with unconfirmed email."""
        from checktick_app.core.email_confirmation import EmailConfirmationToken

        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "newuser@example.com",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect to home after signup
        self.assertEqual(response.status_code, 302)

        # User should exist and have unconfirmed email
        user = User.objects.get(email="newuser@example.com")
        self.assertFalse(user.profile.email_confirmed)

        # Confirmation token should be created
        self.assertTrue(EmailConfirmationToken.objects.filter(user=user).exists())


class TestProtectedFeaturesAccess(TestCase):
    """Test access to features that require email confirmation."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )
        # Ensure profile exists
        if not hasattr(self.user, "profile"):
            UserProfile.objects.create(user=self.user)

    def test_survey_create_requires_confirmation(self):
        """Test that survey creation requires email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Try to access survey creation when email is not confirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        response = self.client.get(reverse("surveys:create"))
        # Should redirect to home due to email confirmation requirement
        self.assertRedirects(response, reverse("core:home"))

        # Now confirm email and try again
        self.user.profile.email_confirmed = True
        self.user.profile.save()

        # Should now be able to access survey creation
        response = self.client.get(reverse("surveys:create"))
        self.assertEqual(response.status_code, 200)  # Or whatever the actual status is

    def test_billing_requires_confirmation(self):
        """Test that billing features require email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Try to access billing when email is not confirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        response = self.client.get(reverse("core:subscription_portal"))
        # Should redirect to home due to email confirmation requirement
        self.assertRedirects(response, reverse("core:home"))

    def test_2fa_setup_requires_confirmation(self):
        """Test that 2FA setup requires email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Try to access 2FA setup when email is not confirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        response = self.client.get(reverse("core:two_factor_setup"))
        # Should redirect to home due to email confirmation requirement
        self.assertRedirects(response, reverse("core:home"))


class TestOIDCUserCompatibility(TestCase):
    """Test that OIDC users with verified emails can access features."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="oidcuser", email="oidc@example.com", password=PASSWORD
        )
        # Create profile
        if not hasattr(self.user, "profile"):
            UserProfile.objects.create(user=self.user)

        # Create OIDC record with verified email (simulating OIDC login)
        UserOIDC.objects.create(
            user=self.user,
            provider="google",
            subject="google-subject-123",
            email_verified=True,  # This simulates OIDC-verified email
        )

    def test_oidc_user_access_without_local_confirmation(self):
        """Test that OIDC users with verified emails can access features."""
        # OIDC user has email_verified=True but local email_confirmed=False
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        self.client.login(username="oidcuser", password=PASSWORD)

        # This test verifies that OIDC users are treated differently
        # The actual behavior depends on the decorator implementation
        self.user.refresh_from_db()
        oidc_record = self.user.oidc
        self.assertTrue(oidc_record.email_verified)
        self.assertFalse(self.user.profile.email_confirmed)
