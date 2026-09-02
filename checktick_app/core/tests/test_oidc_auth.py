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


def test_oidc_callback_view_has_no_provider_get_settings_override():
    """F17: the callback view must NOT carry a per-provider ``get_settings``
    override. Provider resolution lives in the authentication backend
    (``CustomOIDCAuthenticationBackend.authenticate``), where the token
    exchange actually runs. A view-level override would be dead code (the
    view's ``get_settings`` only affects ``LOGIN_REDIRECT_URL`` and
    ``OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS``, neither of which is
    provider-specific) and would reintroduce the pre-existing diagnostic
    about overriding a ``@staticmethod`` with an instance method."""
    # The callback view should inherit the parent's get_settings unchanged.
    assert "get_settings" not in HealthcareOIDCCallbackView.__dict__, (
        "HealthcareOIDCCallbackView must not override get_settings; provider "
        "resolution belongs in CustomOIDCAuthenticationBackend.authenticate."
    )


@pytest.mark.django_db
def test_oidc_backend_uses_azure_endpoints_for_azure_session(client):
    """F17: the authentication backend must use Azure provider endpoints when
    the session provider is Azure. The backend is instantiated fresh by
    Django's ``authenticate()`` and its ``__init__`` reads from global settings
    (which default to Google). The backend's ``authenticate()`` override must
    re-resolve the provider-specific endpoints from ``OIDC_PROVIDERS`` before
    the token exchange runs, otherwise Azure logins would hit Google's token
    endpoint with Azure credentials and fail."""
    from unittest.mock import patch

    from checktick_app.core.auth import CustomOIDCAuthenticationBackend

    factory = RequestFactory()
    request = factory.get("/oidc/callback/?code=test-code&state=test-state")
    request.session = client.session
    request.session["oidc_provider"] = "azure"
    request.session.save()

    backend = CustomOIDCAuthenticationBackend()
    # __init__ reads Google defaults from global settings
    assert backend.OIDC_OP_TOKEN_ENDPOINT == settings.OIDC_OP_TOKEN_ENDPOINT

    # Stub the token exchange / verification / user creation so we can assert
    # on the resolved endpoints without hitting real provider HTTP endpoints.
    captured_payload = {}

    def fake_get_token(payload):
        captured_payload.update(payload)
        return {"id_token": "fake-id-token", "access_token": "fake-access-token"}

    with patch.object(
        CustomOIDCAuthenticationBackend, "get_token", side_effect=fake_get_token
    ), patch.object(
        CustomOIDCAuthenticationBackend, "verify_token", return_value={"sub": "x"}
    ), patch.object(
        CustomOIDCAuthenticationBackend, "get_or_create_user", return_value=None
    ):
        backend.authenticate(request)

    # The token payload must carry the Azure client id/secret, not Google's.
    assert captured_payload["client_id"] == settings.OIDC_RP_CLIENT_ID_AZURE
    assert captured_payload["client_secret"] == settings.OIDC_RP_CLIENT_SECRET_AZURE
    # And the backend's resolved endpoints must be Azure's.
    assert backend.OIDC_OP_TOKEN_ENDPOINT == settings.OIDC_OP_TOKEN_ENDPOINT_AZURE
    assert backend.OIDC_OP_USER_ENDPOINT == settings.OIDC_OP_USER_ENDPOINT_AZURE
    assert backend.OIDC_OP_JWKS_ENDPOINT == settings.OIDC_OP_JWKS_ENDPOINT_AZURE
    assert backend.OIDC_RP_CLIENT_ID == settings.OIDC_RP_CLIENT_ID_AZURE
    assert backend.OIDC_RP_CLIENT_SECRET == settings.OIDC_RP_CLIENT_SECRET_AZURE


@pytest.mark.django_db
def test_oidc_backend_uses_google_endpoints_for_google_session(client):
    """F17: the authentication backend must use Google provider endpoints when
    the session provider is Google (the default)."""
    from unittest.mock import patch

    from checktick_app.core.auth import CustomOIDCAuthenticationBackend

    factory = RequestFactory()
    request = factory.get("/oidc/callback/?code=test-code&state=test-state")
    request.session = client.session
    request.session["oidc_provider"] = "google"
    request.session.save()

    backend = CustomOIDCAuthenticationBackend()

    captured_payload = {}

    def fake_get_token(payload):
        captured_payload.update(payload)
        return {"id_token": "fake-id-token", "access_token": "fake-access-token"}

    with patch.object(
        CustomOIDCAuthenticationBackend, "get_token", side_effect=fake_get_token
    ), patch.object(
        CustomOIDCAuthenticationBackend, "verify_token", return_value={"sub": "x"}
    ), patch.object(
        CustomOIDCAuthenticationBackend, "get_or_create_user", return_value=None
    ):
        backend.authenticate(request)

    assert captured_payload["client_id"] == settings.OIDC_RP_CLIENT_ID_GOOGLE
    assert backend.OIDC_OP_TOKEN_ENDPOINT == settings.OIDC_OP_TOKEN_ENDPOINT
    assert backend.OIDC_RP_CLIENT_ID == settings.OIDC_RP_CLIENT_ID_GOOGLE


@pytest.mark.django_db
class TestProviderDetection:
    """Provider must be detected from the verified ID token issuer (or the
    login session) even though userinfo responses omit the ``iss`` claim.

    Regression: M365/Azure users were stored with provider="unknown" because
    ``_get_provider_from_claims`` only inspected the userinfo response, which
    has no issuer. The stored provider participates in encryption key
    derivation, so detection must be correct at record creation time.
    """

    def _backend_with_session(self, client, provider):
        from checktick_app.core.auth import CustomOIDCAuthenticationBackend

        factory = RequestFactory()
        request = factory.get("/oidc/callback/?code=test-code")
        request.session = client.session
        if provider:
            request.session["oidc_provider"] = provider
        backend = CustomOIDCAuthenticationBackend()
        backend.request = request
        return backend

    def test_azure_issuer_detected(self, client):
        backend = self._backend_with_session(client, None)
        assert (
            backend._get_provider_from_claims(
                {"iss": "https://login.microsoftonline.com/{tenant}/v2.0"}
            )
            == "azure"
        )

    def test_legacy_azure_v1_issuer_detected(self, client):
        backend = self._backend_with_session(client, None)
        assert (
            backend._get_provider_from_claims(
                {"iss": "https://sts.windows.net/<tenant-guid>/"}
            )
            == "azure"
        )

    def test_google_issuer_detected(self, client):
        backend = self._backend_with_session(client, None)
        assert (
            backend._get_provider_from_claims({"iss": "https://accounts.google.com"})
            == "google"
        )

    def test_session_fallback_when_issuer_missing(self, client):
        """Userinfo responses lack ``iss``; the login-session provider is used."""
        backend = self._backend_with_session(client, "azure")
        assert backend._get_provider_from_claims({}) == "azure"

    def test_unknown_when_no_issuer_and_no_session(self, client):
        backend = self._backend_with_session(client, None)
        assert backend._get_provider_from_claims({}) == "unknown"

    def test_spoofed_issuer_substring_not_matched(self, client):
        """A hostile issuer embedding a known host anywhere other than the
        hostname must NOT be treated as that provider (CodeQL
        py/incomplete-url-substring-sanitization)."""
        backend = self._backend_with_session(client, None)
        assert (
            backend._get_provider_from_claims(
                {"iss": "https://evil.example/?iss=login.microsoftonline.com"}
            )
            == "unknown"
        )
        assert (
            backend._get_provider_from_claims(
                {"iss": "https://login.microsoftonline.com.evil.example/"}
            )
            == "unknown"
        )
        assert (
            backend._get_provider_from_claims(
                {"iss": "https://evil.com/accounts.google.com"}
            )
            == "unknown"
        )

    def test_get_or_create_user_persists_azure_provider(self, client):
        """End-to-end: an M365 login with no ``iss`` in userinfo stores
        provider="azure" (seeded from the verified ID token payload)."""
        from checktick_app.core.auth import CustomOIDCAuthenticationBackend

        backend = self._backend_with_session(client, "azure")

        userinfo = {  # Microsoft Graph userinfo: no ``iss`` claim
            "email": "m365user@example.com",
            "sub": "azure-sub-1",
        }
        id_token_payload = {
            "iss": "https://login.microsoftonline.com/<tenant>/v2.0",
            "sub": "azure-sub-1",
            "email": "m365user@example.com",
        }

        with patch.object(
            CustomOIDCAuthenticationBackend, "get_userinfo", return_value=userinfo
        ):
            user = backend.get_or_create_user("tok", "id-token", id_token_payload)

        assert user is not None
        record = UserOIDC.objects.get(user=user)
        assert record.provider == "azure"
        assert record.subject == "azure-sub-1"
