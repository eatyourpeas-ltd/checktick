"""
Tests for OIDC authentication flow.

These tests verify that the OIDC authentication callback properly
handles success and failure cases, ensuring no unauthorized access
is granted when authentication fails.

Also covers the August 2026 security review OIDC findings:

* F10 — The OIDC login entry point must not propagate an unvalidated
  ``next`` parameter into SSO/traditional-login hrefs (same
  open-redirect class as F1). The original finding located the issue
  in a dead ``HealthcareLoginView`` that was never wired into the URL
  config and would have crashed with ``NoReverseMatch`` if called.
  Remediation removed that dead code; the live login page is
  ``/accounts/login/`` served by ``TwoFactorLoginView`` (a subclass of
  Django's ``LoginView``), whose ``get_context_data`` only exposes
  ``next`` via ``get_redirect_url`` → ``url_has_allowed_host_and_scheme``.
* F17 — The OIDC callback view must not mutate the process-global
  ``django.conf.settings`` object to switch between Google and Azure
  providers; provider config must be resolved per-request so concurrent
  callbacks cannot race on shared global state.
"""

from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory
import pytest

from checktick_app.core import oidc_views
from checktick_app.core.models import UserOIDC
from checktick_app.core.oidc_views import HealthcareOIDCCallbackView

User = get_user_model()


@pytest.mark.django_db
class TestOIDCAuthenticationCallback:
    """Test OIDC authentication callback security."""

    def test_failed_authentication_blocks_access(self, client):
        """
        Test that failed OIDC authentication explicitly redirects to login
        and does NOT grant any access.

        This is a critical security test - if OIDC authentication fails,
        the user should not be authenticated.
        """
        # Create a mock OIDC callback view
        factory = RequestFactory()
        request = factory.get("/oidc/callback/?error=access_denied")
        request.session = client.session
        request.session["oidc_provider"] = "google"

        view = HealthcareOIDCCallbackView()

        # Mock the parent get method to simulate failed authentication
        with patch.object(
            HealthcareOIDCCallbackView.__bases__[0],
            "get",
            return_value=Mock(status_code=302),
        ):
            # Set request.user to AnonymousUser (authentication failed)
            from django.contrib.auth.models import AnonymousUser

            request.user = AnonymousUser()

            # Call the callback
            response = view.get(request)

            # Verify user is NOT authenticated
            assert not request.user.is_authenticated

            # Verify redirect to login with error
            assert response.status_code == 302
            assert "/accounts/login/" in response.url
            assert "error=oidc_authentication_failed" in response.url

    def test_successful_authentication_grants_access(self, client):
        """
        Test that successful OIDC authentication properly authenticates
        the user and grants access.
        """
        # Create a test user
        user = User.objects.create_user(
            username="test@example.com", email="test@example.com"
        )

        # Create UserOIDC record
        UserOIDC.objects.create(
            user=user,
            provider="google",
            subject="google-subject-123",
            email_verified=True,
            signup_completed=True,
        )

        factory = RequestFactory()
        request = factory.get("/oidc/callback/?code=test-code")
        request.session = client.session
        request.session["oidc_provider"] = "google"

        view = HealthcareOIDCCallbackView()

        # Mock the parent get method to simulate successful authentication
        with patch.object(
            HealthcareOIDCCallbackView.__bases__[0],
            "get",
            return_value=Mock(status_code=302, get=lambda x: "/"),
        ):
            # Set request.user to the authenticated user
            request.user = user

            # Call the callback
            view.get(request)

            # Verify user IS authenticated
            assert request.user.is_authenticated
            assert request.user.email == "test@example.com"

    def test_exception_during_authentication_blocks_access(self, client):
        """
        Test that exceptions during OIDC authentication don't grant access.

        If an exception occurs during the callback, the user should be
        redirected to login, not left in an authenticated state.
        """
        factory = RequestFactory()
        request = factory.get("/oidc/callback/?code=test-code")
        request.session = client.session
        request.session["oidc_provider"] = "google"

        view = HealthcareOIDCCallbackView()

        # Mock the parent get method to raise an exception
        with patch.object(
            HealthcareOIDCCallbackView.__bases__[0],
            "get",
            side_effect=Exception("OIDC provider error"),
        ):
            from django.contrib.auth.models import AnonymousUser

            request.user = AnonymousUser()

            # Call the callback
            response = view.get(request)

            # Verify user is NOT authenticated
            assert not request.user.is_authenticated

            # Verify redirect to login with error
            assert response.status_code == 302
            assert "/accounts/login/" in response.url
            assert "error=" in response.url

    def test_unauthenticated_user_cannot_access_protected_views(self, client):
        """
        Integration test: Verify that unauthenticated users (including
        those whose OIDC authentication failed) cannot access protected views.
        """
        # Try to access a protected view without authentication
        from django.urls import reverse

        # Create a test survey
        owner = User.objects.create_user(username="owner", email="owner@example.com")
        from checktick_app.surveys.models import Survey

        Survey.objects.create(owner=owner, name="Test", slug="test")

        # Try to access the dashboard without authentication
        response = client.get(reverse("surveys:dashboard", kwargs={"slug": "test"}))

        # Should be redirected or get 403
        assert response.status_code in (302, 403)

        # If redirected, should be to login
        if response.status_code == 302:
            assert "/accounts/login" in response.url or response.url.startswith(
                "/accounts/login"
            )


# ---------------------------------------------------------------------------
# F10 — OIDC login ``next`` parameter must be validated
# ---------------------------------------------------------------------------


def test_dead_healthcare_login_view_removed():
    """F10: the dead ``HealthcareLoginView`` (which passed an unvalidated
    ``next`` straight into the template context and used a non-existent
    ``oidc:`` reverse namespace) must stay removed. Re-introducing it would
    resurrect the F10 open-redirect class. The live login page is
    ``/accounts/login/`` served by ``TwoFactorLoginView``."""
    assert not hasattr(oidc_views, "HealthcareLoginView"), (
        "HealthcareLoginView was removed as the F10 remediation; the live "
        "login page is /accounts/login/ (TwoFactorLoginView). Do not "
        "re-introduce a parallel login view that bypasses Django's "
        "LoginView.get_redirect_url() validation."
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "next_url",
    [
        "//evil.example/phish",
        "/\\\\evil.example/phish",
        "https://evil.example/phish",
    ],
)
def test_live_login_page_does_not_leak_unsafe_next_into_sso_links(client, next_url):
    """F10 regression guard: the live login page (``/accounts/login/``) is
    served by ``TwoFactorLoginView`` (a ``LoginView`` subclass). Django's
    ``LoginView.get_context_data`` only exposes ``next`` via
    ``get_redirect_url()``, which validates with
    ``url_has_allowed_host_and_scheme`` and returns ``""`` for unsafe
    values. So an unsafe ``next`` must NOT appear in the rendered SSO
    hrefs or the traditional-login form's hidden field."""
    response = client.get(f"/accounts/login/?next={next_url}")
    assert response.status_code == 200
    body = response.content.decode("utf-8")

    # The unsafe value must NOT appear verbatim anywhere in the page.
    assert (
        next_url not in body
    ), f"unsafe next value {next_url!r} leaked into login page body"
    # The SSO hrefs must not carry an unsafe next either. The template
    # renders ``&next={{ next|urlencode }}`` only when ``next`` is truthy;
    # Django's LoginView sets it to "" for unsafe values, so the ``{% if %}``
    # guard omits the parameter entirely.
    assert "next=//evil" not in body
    assert "next=https%3A%2F%2Fevil" not in body


@pytest.mark.django_db
def test_live_login_page_preserves_safe_next(client):
    """F10 regression guard: legitimate relative ``next`` URLs must still
    propagate so users land on the survey they came from after login."""
    response = client.get("/accounts/login/?next=/surveys/demo/take/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "/surveys/demo/take/" in body


# ---------------------------------------------------------------------------
# F17 — OIDC callback view must not mutate global settings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_oidc_callback_does_not_mutate_global_settings_for_azure(client):
    """F17: the Azure callback path must not overwrite the process-global
    ``settings.OIDC_RP_CLIENT_ID`` (and friends).

    Before the fix, ``HealthcareOIDCCallbackView.get`` mutated
    ``django.conf.settings`` in a try/finally block to swap Google defaults
    for Azure values. In a threaded server two concurrent callbacks (one
    Google, one Azure) could race on these attributes, causing intermittent
    auth failures or token validation against the wrong provider. The fix
    resolves provider config per-request via ``get_settings`` and never
    touches the global settings object.
    """
    snapshot_keys = [
        "OIDC_RP_CLIENT_ID",
        "OIDC_RP_CLIENT_SECRET",
        "OIDC_OP_TOKEN_ENDPOINT",
        "OIDC_OP_USER_ENDPOINT",
        "OIDC_OP_JWKS_ENDPOINT",
        "OIDC_RP_SCOPES",
    ]
    before = {k: getattr(settings, k) for k in snapshot_keys}

    factory = RequestFactory()
    request = factory.get("/oidc/callback/?code=test-code&state=test-state")
    request.session = client.session
    request.session["oidc_provider"] = "azure"
    request.session.save()

    view = HealthcareOIDCCallbackView()

    with patch.object(
        HealthcareOIDCCallbackView.__bases__[0],
        "get",
        return_value=Mock(status_code=302, get=lambda x: "/surveys/"),
    ):
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        view.get(request)

    after = {k: getattr(settings, k) for k in snapshot_keys}
    assert before == after, (
        "OIDC callback mutated global settings; provider config must be "
        f"resolved per-request. Before={before!r} After={after!r}"
    )


@pytest.mark.django_db
def test_oidc_callback_resolves_azure_provider_config_per_request(client):
    """F17: when the session provider is Azure, the callback view's
    ``get_settings`` must return the Azure values (not the Google defaults
    stored on the global settings object)."""
    factory = RequestFactory()
    request = factory.get("/oidc/callback/?code=test-code&state=test-state")
    request.session = client.session
    request.session["oidc_provider"] = "azure"
    request.session.save()

    view = HealthcareOIDCCallbackView()
    view.request = request

    resolved = view.get_settings("OIDC_RP_CLIENT_ID")
    assert resolved == settings.OIDC_RP_CLIENT_ID_AZURE
    assert resolved != settings.OIDC_RP_CLIENT_ID


@pytest.mark.django_db
def test_oidc_callback_resolves_google_provider_config_per_request(client):
    """F17: when the session provider is Google (the default), the callback
    view's ``get_settings`` must return the Google values."""
    factory = RequestFactory()
    request = factory.get("/oidc/callback/?code=test-code&state=test-state")
    request.session = client.session
    request.session["oidc_provider"] = "google"
    request.session.save()

    view = HealthcareOIDCCallbackView()
    view.request = request

    resolved = view.get_settings("OIDC_RP_CLIENT_ID")
    assert resolved == settings.OIDC_RP_CLIENT_ID_GOOGLE
