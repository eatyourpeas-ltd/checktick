"""Regression tests for Require2FAMiddleware redirect behaviour.

Discovered on the Civo staging POC: an authenticated password user with
unconfirmed email and no 2FA device entered a redirect cycle —
Require2FAMiddleware sent every non-exempt page to /2fa/setup/, the setup
view's email_confirmed_required decorator sent it back to core:home, and
/home was not exempt, so the middleware fired again:

    /surveys/ -> /2fa/setup/ -> /home -> /2fa/setup/ -> ...

Django's test client raises RedirectCycleError on exactly that shape,
which makes "follow the chain and it must terminate on a rendered page"
a crisp regression assertion. REQUIRE_2FA is off during normal test runs
(settings: default=not TESTING), so these tests enable it explicitly.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from checktick_app.core.email_confirmation import EmailConfirmationManager
from checktick_app.core.views_2fa import is_password_user

User = get_user_model()

PASSWORD = "testpass123"


class Require2FAMiddlewareLoopTests(TestCase):
    """The unconfirmed-email + no-2FA state must terminate, not cycle."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="loopprobe", email="loopprobe@example.com", password=PASSWORD
        )
        self.user.profile.email_confirmed = False
        self.user.profile.save()
        self.client.login(username="loopprobe", password=PASSWORD)

    @override_settings(REQUIRE_2FA=True)
    def test_unconfirmed_password_user_terminates_on_home(self):
        """GET /surveys/ must land on a rendered page, never a redirect cycle.

        Pre-fix this raised RedirectCycleError.
        """
        response = self.client.get(reverse("surveys:list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.redirect_chain)
        # The designed destination: home renders the "confirm your email"
        # notice for exactly this account state.
        self.assertEqual(response.redirect_chain[-1][0], reverse("core:home"))

    @override_settings(REQUIRE_2FA=True)
    def test_confirmation_link_reachable_while_gated(self):
        """The emailed confirmation link must work for a gated, logged-in user.

        Pre-fix the link was bounced to /2fa/setup/ by the middleware and
        the token never got verified.
        """
        token, success, _error_info = EmailConfirmationManager.send_confirmation_email(
            self.user
        )
        self.assertTrue(success)

        response = self.client.get(reverse("confirm_email", args=[token]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_confirmed)

    @override_settings(REQUIRE_2FA=True)
    def test_resend_confirmation_reachable_while_gated(self):
        """The self-service resend endpoint must stay reachable while gated."""
        response = self.client.get(reverse("resend_confirmation"), follow=True)
        self.assertEqual(response.status_code, 200)
        # It redirects to home (exempt) with a message.
        self.assertEqual(response.redirect_chain[-1][0], reverse("core:home"))

    @override_settings(REQUIRE_2FA=True)
    def test_home_offers_resend_action_while_gated(self):
        """The page gated users land on must offer a working resend action.

        The 2FA gate makes /profile/ unreachable for exactly this account
        state, so the old "resend via Profile" instruction was a dead end.
        Home (where the middleware and email_confirmed_required send the
        user) must carry the resend action itself, posting to the exempt
        dedicated route.
        """
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        # The resend form posts to the middleware-exempt route.
        self.assertContains(response, reverse("resend_confirmation"))
        self.assertContains(response, "Resend confirmation email")
        # The gated Profile path must no longer be advertised on home.
        self.assertNotContains(response, "Email Notification Preferences")

    @override_settings(REQUIRE_2FA=True)
    def test_resend_button_flow_sends_email_while_gated(self):
        """POSTing the home resend form must deliver the confirmation email."""
        from django.core import mail

        response = self.client.post(reverse("resend_confirmation"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse("core:home"))
        self.assertTrue(
            any("confirm" in email.subject.lower() for email in mail.outbox),
            "Resend confirmation email was not sent while gated",
        )

    @override_settings(REQUIRE_2FA=True)
    def test_confirmed_password_user_is_sent_to_setup_exactly_once(self):
        """With email confirmed, the user must reach the setup page itself.

        This guards the other side of the fix: the middleware still
        enforces 2FA (single redirect to the exempt setup page, which now
        renders instead of bouncing back to home).
        """
        self.user.profile.email_confirmed = True
        self.user.profile.save()

        response = self.client.get(reverse("surveys:list"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain[-1][0], reverse("core:two_factor_setup")
        )


class IsPasswordUserTests(TestCase):
    """is_password_user must classify OIDC-provisioned accounts as SSO."""

    def test_empty_password_is_not_a_password_user(self):
        """OIDC-provisioned accounts keep the model's empty-string password."""
        user = User.objects.create(username="sso_probe", email="sso@example.com")
        try:
            self.assertEqual(user.password, "")
            # Django quirk this guards against: is_password_usable("") is True
            self.assertTrue(user.has_usable_password())
            self.assertFalse(is_password_user(user))
        finally:
            user.delete()

    def test_real_password_is_a_password_user(self):
        user = User.objects.create_user(
            username="pw_probe", email="pw@example.com", password=PASSWORD
        )
        try:
            self.assertTrue(is_password_user(user))
        finally:
            user.delete()

    def test_unusable_password_is_not_a_password_user(self):
        user = User.objects.create_user(
            username="unusable_probe", email="unusable@example.com", password=PASSWORD
        )
        try:
            user.set_unusable_password()
            self.assertFalse(is_password_user(user))
        finally:
            user.delete()
