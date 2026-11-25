"""Signup bot-gating tests: hCaptcha enforcement and per-IP rate limiting.

The signup view fails closed when ``HCAPTCHA_SECRET`` is configured (issue
#382): no verified captcha token, no account. These tests exercise the real
``verify_captcha`` path by patching only the outbound siteverify HTTP call.

The per-IP rate limit (10 signups/hour, POST only) backstops the captcha for
sophisticated bots that solve challenges: found live 2026-11-25 with ~200
bot signups (many targeting real third-party addresses), so the limit is on
the POST only — browsing the signup form is never throttled.
"""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

SIGNUP_URL = "core:signup"

VALID_DATA = {
    "email": "newuser@example.com",
    "email_confirm": "newuser@example.com",
    "password1": "testpass123!",  # nosec: test password
    "password2": "testpass123!",  # nosec: test password
}


def _data(email: str) -> dict:
    return {**VALID_DATA, "email": email, "email_confirm": email}


def _siteverify(ok: bool):
    """Mock the hCaptcha siteverify HTTP response (urllib context manager)."""
    resp = mock.MagicMock()
    resp.read.return_value = json.dumps({"success": ok}).encode()
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = resp
    return ctx


URLOPEN = "checktick_app.core.captcha.urllib.request.urlopen"


class SignupCaptchaTests(TestCase):
    """hCaptcha is enforced fail-closed on signup when configured."""

    @override_settings(HCAPTCHA_SECRET="test-secret")
    @mock.patch(URLOPEN)
    def test_signup_without_captcha_token_is_blocked(self, mock_urlopen):
        """No token in the POST → siteverify not even called, no account."""
        response = self.client.post(reverse(SIGNUP_URL), _data("blocked@example.com"))

        self.assertEqual(User.objects.filter(email="blocked@example.com").count(), 0)
        mock_urlopen.assert_not_called()
        self.assertContains(response, "CAPTCHA verification failed")

    @override_settings(HCAPTCHA_SECRET="test-secret")
    @mock.patch(URLOPEN)
    def test_signup_with_rejected_token_is_blocked(self, mock_urlopen):
        """A failed/used token → siteverify says no → no account."""
        mock_urlopen.return_value = _siteverify(ok=False)

        response = self.client.post(
            reverse(SIGNUP_URL),
            {**_data("rejected@example.com"), "h-captcha-response": "bad-token"},
        )

        self.assertEqual(User.objects.filter(email="rejected@example.com").count(), 0)
        mock_urlopen.assert_called_once()
        self.assertContains(response, "CAPTCHA verification failed")

    @override_settings(HCAPTCHA_SECRET="test-secret")
    @mock.patch(URLOPEN)
    def test_signup_with_valid_token_creates_account(self, mock_urlopen):
        """A verified token → the account is created (real verify path)."""
        mock_urlopen.return_value = _siteverify(ok=True)

        response = self.client.post(
            reverse(SIGNUP_URL),
            {**_data("verified@example.com"), "h-captcha-response": "good-token"},
        )

        self.assertRedirects(
            response, reverse("core:home"), fetch_redirect_response=False
        )
        self.assertTrue(User.objects.filter(email="verified@example.com").exists())

    def test_signup_without_captcha_config_does_not_require_token(self):
        """An unset HCAPTCHA_SECRET disables the check (self-host convention)."""
        response = self.client.post(reverse(SIGNUP_URL), _data("nocaptcha@example.com"))

        self.assertRedirects(
            response, reverse("core:home"), fetch_redirect_response=False
        )
        self.assertTrue(User.objects.filter(email="nocaptcha@example.com").exists())

    @override_settings(HCAPTCHA_SITEKEY="test-sitekey")
    def test_captcha_widget_rendered_when_sitekey_configured(self):
        response = self.client.get(reverse(SIGNUP_URL))
        self.assertContains(response, "h-captcha")
        self.assertContains(response, "test-sitekey")

    def test_captcha_widget_absent_without_sitekey(self):
        response = self.client.get(reverse(SIGNUP_URL))
        self.assertNotContains(response, "h-captcha")


class SignupRateLimitTests(TestCase):
    """Per-IP signup throttle: 10 POSTs/hour, GET never throttled.

    Each method re-applies ``override_settings(RATELIMIT_ENABLE=True)`` at
    method level on purpose: the autouse
    ``_ratelimit_disabled_by_default`` conftest fixture runs after
    ``setUpClass`` and would clobber a class-level override, while a
    method-level one activates after fixtures and wins.
    """

    @override_settings(RATELIMIT_ENABLE=True)
    def test_eleventh_signup_from_same_ip_is_blocked(self):
        for i in range(10):
            response = self.client.post(
                reverse(SIGNUP_URL), _data(f"rl{i}@example.com")
            )
            self.assertRedirects(
                response, reverse("core:home"), fetch_redirect_response=False
            )
        self.assertEqual(User.objects.filter(email__startswith="rl").count(), 10)

        # The 11th POST from the same IP is blocked (403, house style for
        # block=True) and creates no account.
        response = self.client.post(reverse(SIGNUP_URL), _data("rl11@example.com"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.filter(email="rl11@example.com").count(), 0)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_get_signup_page_not_throttled_after_limit(self):
        """Browsing the form is never throttled — only account creation."""
        for i in range(12):
            self.client.post(reverse(SIGNUP_URL), _data(f"rlg{i}@example.com"))
        response = self.client.get(reverse(SIGNUP_URL))
        self.assertEqual(response.status_code, 200)
