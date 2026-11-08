"""Signup captcha enforcement (issue #382).

hCaptcha must gate the email/password signup flow whenever
HCAPTCHA_SECRET is configured (fail closed). An unset secret keeps signup
captcha-free for self-hosters and tests — the same convention as the
survey-response flow (checktick_app/core/captcha.py).
"""

import json

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.captcha import verify_captcha

TEST_PASSWORD = "ComplexTestPassword123!"


def _signup_data(email):
    return {
        "email": email,
        "email_confirm": email,
        "password1": TEST_PASSWORD,
        "password2": TEST_PASSWORD,
        "account_type": "simple",
    }


def _mock_signup_emails(monkeypatch):
    """Keep the signup success path offline (no confirmation/welcome mail)."""
    monkeypatch.setattr(
        "checktick_app.core.views.EmailConfirmationManager.send_confirmation_email",
        lambda user, request: (None, True, None),
    )
    monkeypatch.setattr(
        "checktick_app.core.email_utils.send_welcome_email", lambda user: True
    )


class _FakeSiteverifyResponse:
    """Minimal stand-in for the urlopen context manager in captcha.py."""

    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_siteverify(monkeypatch, payload):
    def _fake_urlopen(*args, **kwargs):
        return _FakeSiteverifyResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)


@pytest.mark.django_db
def test_signup_blocked_without_captcha_token_when_secret_set(client, settings):
    """Fail closed: with HCAPTCHA_SECRET set, a missing token means no account."""
    settings.HCAPTCHA_SECRET = "dummy-secret"

    resp = client.post(
        reverse("core:signup"), data=_signup_data("captcha-none@example.com")
    )

    assert resp.status_code == 200  # re-rendered form, not a redirect
    assert "CAPTCHA verification failed" in resp.content.decode()
    assert (
        not get_user_model().objects.filter(email="captcha-none@example.com").exists()
    )


@pytest.mark.django_db
def test_signup_blocked_when_siteverify_rejects_token(client, settings, monkeypatch):
    """A token that hCaptcha rejects must not create an account."""
    settings.HCAPTCHA_SECRET = "dummy-secret"
    _mock_siteverify(monkeypatch, {"success": False})

    data = _signup_data("captcha-reject@example.com")
    data["h-captcha-response"] = "bad-token"
    resp = client.post(reverse("core:signup"), data=data)

    assert resp.status_code == 200
    assert (
        not get_user_model().objects.filter(email="captcha-reject@example.com").exists()
    )


@pytest.mark.django_db
def test_signup_succeeds_with_verified_token(client, settings, monkeypatch):
    """A verified token lets the signup through while the secret is set."""
    settings.HCAPTCHA_SECRET = "dummy-secret"
    _mock_siteverify(monkeypatch, {"success": True})
    _mock_signup_emails(monkeypatch)

    data = _signup_data("captcha-pass@example.com")
    data["h-captcha-response"] = "good-token"
    resp = client.post(reverse("core:signup"), data=data)

    assert resp.status_code == 302
    assert get_user_model().objects.filter(email="captcha-pass@example.com").exists()


@pytest.mark.django_db
def test_signup_succeeds_without_secret_configured(client, settings, monkeypatch):
    """Unset HCAPTCHA_SECRET disables the captcha (self-hoster convention)."""
    settings.HCAPTCHA_SECRET = ""
    _mock_signup_emails(monkeypatch)

    resp = client.post(
        reverse("core:signup"), data=_signup_data("captcha-off@example.com")
    )

    assert resp.status_code == 302
    assert get_user_model().objects.filter(email="captcha-off@example.com").exists()


@pytest.mark.django_db
def test_signup_page_renders_captcha_widget_only_when_sitekey_set(client, settings):
    """The widget appears on the signup form only when hCaptcha is configured."""
    settings.HCAPTCHA_SITEKEY = "dummy-sitekey"
    html = client.get(reverse("core:signup")).content.decode()
    assert 'data-sitekey="dummy-sitekey"' in html

    settings.HCAPTCHA_SITEKEY = ""
    html = client.get(reverse("core:signup")).content.decode()
    assert "data-sitekey" not in html


def test_verify_captcha_passes_when_secret_unset(rf, settings):
    """No secret configured -> captcha disabled -> verification passes."""
    settings.HCAPTCHA_SECRET = ""
    assert verify_captcha(rf.post("/")) is True


def test_verify_captcha_fails_closed_on_siteverify_error(rf, settings, monkeypatch):
    """A secret is set but siteverify is unreachable -> fail closed."""
    settings.HCAPTCHA_SECRET = "dummy-secret"

    def _unreachable(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", _unreachable)
    assert verify_captcha(rf.post("/", {"h-captcha-response": "some-token"})) is False
