"""Integration tests for email confirmation functionality."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = "testpass123"


class TestEmailConfirmationIntegration(TestCase):
    """Test the overall email confirmation integration."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password=PASSWORD
        )
        # Ensure profile exists
        if not hasattr(self.user, "profile"):
            from checktick_app.core.models import UserProfile

            UserProfile.objects.create(user=self.user)

    def test_user_profile_has_email_confirmed_field(self):
        """Test that UserProfile has the email_confirmed field."""
        profile = self.user.profile
        self.assertFalse(profile.email_confirmed)  # Default should be False

        # Update the field
        profile.email_confirmed = True
        profile.save()

        # Verify it was updated
        profile.refresh_from_db()
        self.assertTrue(profile.email_confirmed)

    def test_signup_creates_user_with_unconfirmed_email(self):
        """Test that signup creates a user with unconfirmed email."""
        response = self.client.post(
            reverse("core:signup"),
            {
                "email": "newuser@example.com",
                "password1": "complexpassword123!",
                "password2": "complexpassword123!",
            },
        )

        # Should redirect somewhere after signup
        self.assertEqual(response.status_code, 302)

        # User should exist
        user = User.objects.get(email="newuser@example.com")
        # Email should be unconfirmed initially
        self.assertFalse(user.profile.email_confirmed)

    def test_protected_features_require_confirmation(self):
        """Test that protected features require email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Set email as unconfirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        # Try to access survey creation
        response = self.client.get(reverse("surveys:create"))
        # Should redirect to home due to email confirmation requirement
        self.assertRedirects(response, reverse("core:home"))

        # Set email as confirmed
        self.user.profile.email_confirmed = True
        self.user.profile.save()

        # Now should be able to access survey creation (will get 200 or form)
        response = self.client.get(reverse("surveys:create"))
        # This might be 200 (success) or 403 (permission denied for other reasons)
        # but it shouldn't redirect to home anymore
        self.assertNotEqual(response.status_code, 302)
        if response.status_code == 302:
            # If it redirects, it shouldn't be to home (unless other checks apply)
            self.assertNotEqual(response.url, reverse("core:home"))

    def test_billing_features_require_confirmation(self):
        """Test that billing features require email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Set email as unconfirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        # Try to access billing
        response = self.client.get(reverse("core:subscription_portal"))
        # Should redirect to home due to email confirmation requirement
        self.assertRedirects(response, reverse("core:home"))

    def test_2fa_features_require_confirmation(self):
        """Test that 2FA features require email confirmation."""
        self.client.login(username="testuser", password=PASSWORD)

        # Set email as unconfirmed
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        # Try to access 2FA setup
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
            from checktick_app.core.models import UserProfile

            UserProfile.objects.create(user=self.user)

        # Create OIDC record with verified email (simulating OIDC login)
        from checktick_app.core.models import UserOIDC

        UserOIDC.objects.create(
            user=self.user,
            provider="google",
            subject="google-subject-123",
            email_verified=True,  # This simulates OIDC-verified email
        )

    def test_oidc_user_can_access_features_without_local_confirmation(self):
        """Test that OIDC users with verified emails can access features."""
        # OIDC user has email_verified=True but local email_confirmed=False
        self.user.profile.email_confirmed = False
        self.user.profile.save()

        self.client.login(username="oidcuser", password=PASSWORD)

        # OIDC users with verified emails should be able to access features
        # even if local email is not confirmed
        response = self.client.get(reverse("surveys:create"))

        # Should not redirect to home (should either get 200 or other non-redirect status)
        # This depends on other permissions but should not be blocked by email confirmation
        if response.status_code == 302:
            # If it redirects, it shouldn't be to home (due to email confirmation)
            self.assertNotEqual(response.url, reverse("core:home"))
