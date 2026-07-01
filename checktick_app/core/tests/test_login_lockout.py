import secrets

from axes.models import AccessAttempt
from django.urls import reverse
import pytest

LOGIN_IP = "203.0.113.42"
PASSWORD = "correct-password-123"


@pytest.fixture(autouse=True)
def clear_axes_attempts():
    """Keep Axes state isolated for these login-lockout tests."""
    AccessAttempt.objects.all().delete()
    yield
    AccessAttempt.objects.all().delete()


@pytest.fixture
def known_user(django_user_model):
    unique = secrets.token_hex(8)
    email = f"lockout-{unique}@example.com"
    return django_user_model.objects.create_user(
        username=email,
        email=email,
        password=PASSWORD,
    )


@pytest.fixture
def axes_login_settings(settings):
    """Use production-like Axes behavior, without localhost whitelisting."""
    settings.AXES_ENABLED = True
    settings.AXES_IP_WHITELIST = []
    settings.RATELIMIT_ENABLE = False
    return settings


def post_login(client, username, password, ip_address=LOGIN_IP):
    return client.post(
        reverse("login"),
        {"username": username, "password": password},
        REMOTE_ADDR=ip_address,
    )


@pytest.mark.django_db
class TestLoginLockout:
    def test_axes_locks_accounts_by_username_not_standalone_ip(self, settings):
        """Account lockout should be based on the submitted email address.

        IP-based credential-stuffing protection should be handled separately so a
        shared office/NAT/proxy IP cannot force known users straight to the
        account lockout page.
        """
        params = settings.AXES_LOCKOUT_PARAMETERS
        assert params == [["username"]]
        assert ["ip_address"] not in params
        assert settings.AXES_RESET_ON_SUCCESS is True

    def test_ip_failures_for_other_usernames_do_not_lock_known_account_immediately(
        self, client, known_user, axes_login_settings
    ):
        """A saturated source IP must not consume a known account's own attempts."""
        for index in range(axes_login_settings.AXES_FAILURE_LIMIT):
            response = post_login(
                client,
                username=f"unknown-{index}-{secrets.token_hex(4)}@example.com",
                password="wrong-password",
            )
            assert response.status_code in (
                200,
                axes_login_settings.AXES_HTTP_RESPONSE_CODE,
            )

        response = post_login(
            client,
            username=known_user.email,
            password="wrong-password",
        )

        assert response.status_code == 200
        assert b"Login" in response.content

    def test_successful_login_resets_prior_failed_attempts(
        self, client, known_user, axes_login_settings
    ):
        """A successful login should clear previous failures for that account."""
        for _ in range(axes_login_settings.AXES_FAILURE_LIMIT - 1):
            response = post_login(
                client,
                username=known_user.email,
                password="wrong-password",
            )
            assert response.status_code == 200

        response = post_login(
            client,
            username=known_user.email,
            password=PASSWORD,
        )
        assert response.status_code == 302

        client.logout()

        response = post_login(
            client,
            username=known_user.email,
            password="wrong-password",
        )

        assert response.status_code == 200
        assert b"Login" in response.content
