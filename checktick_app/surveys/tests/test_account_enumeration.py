"""
Security tests — account enumeration (Pentest Finding #6, March 2026).

This module verifies that no publicly-accessible or lightly-privileged endpoint
reveals whether a given email address is registered.

Findings covered
----------------
6a  Signup form — previously returned "An account with this email already
    exists"; now returns a non-disclosing generic message.

6b  org_setup view — previously passed ``existing_user=True`` to the template
    and showed a distinctive error; now uses a uniform message and neutral form.

6c  org_users / survey_users views — previously silently did nothing when the
    supplied email matched no account (success=user exists, silence=doesn't);
    now both views return an explicit error message regardless of existence.

Brute-force lockout
-------------------
Also checks that ``AXES_LOCKOUT_PARAMETERS`` is configured as a list-of-lists
so that axes tracks *username* and *IP* independently.  The previous flat-list
format locked only on the combination (username AND ip_address), which allowed
an attacker to bypass the per-account lockout by rotating source IP addresses.

Timing side-channel (org_setup)
--------------------------------
A structural test confirms that ``User().set_password()`` is invoked on the
code path for an unknown email in ``org_setup``, preventing a fast return that
would differ measurably from the existing-user + ``authenticate()`` path.
"""

from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable django-ratelimit for all tests in this module."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture(autouse=True)
def disable_axes(settings):
    """Disable django-axes lockout tracking during these tests."""
    settings.AXES_ENABLED = False


@pytest.fixture
def existing_user(django_user_model):
    return django_user_model.objects.create_user(
        username="existing@example.com",
        email="existing@example.com",
        password="correct-horse-battery",
    )


@pytest.fixture
def org_admin(django_user_model):
    user = django_user_model.objects.create_user(
        username="orgadmin@example.com",
        email="orgadmin@example.com",
        password="adminpassword",
    )
    # Give org_admin an ORGANIZATION tier so collaboration tier-limits don't
    # block the survey_users happy-path tests.
    profile = UserProfile.get_or_create_for_user(user)
    profile.account_tier = UserProfile.AccountTier.ORGANIZATION
    profile.save(update_fields=["account_tier"])
    return user


@pytest.fixture
def org(org_admin):
    o = Organization.objects.create(name="Test Org", owner=org_admin)
    OrganizationMembership.objects.create(
        organization=o,
        user=org_admin,
        role=OrganizationMembership.Role.ADMIN,
    )
    return o


@pytest.fixture
def survey(org_admin, org):
    return Survey.objects.create(
        owner=org_admin,
        organization=org,
        name="Test Survey",
        slug="enum-test-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
    )


# ---------------------------------------------------------------------------
# Finding 6a — Signup form must not confirm account existence
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSignupEnumeration:
    """POST /signup/ must not reveal whether an email is already registered."""

    def test_duplicate_email_uses_generic_message(self, client, existing_user):
        """
        Error for a duplicate email must not contain phrases like
        'already exists' or similar account-confirming language.
        """
        url = reverse("core:signup")
        response = client.post(
            url,
            {
                "email": "existing@example.com",
                "password1": "strongpassword123",
                "password2": "strongpassword123",
            },
        )
        content = response.content.decode()

        # Must NOT contain anything confirming the account was found.
        assert "already exists" not in content.lower()
        assert "an account with this email" not in content.lower()
        assert "sign in instead" not in content.lower()

    def test_duplicate_email_shows_non_disclosing_message(self, client, existing_user):
        """The replacement message must be present so the form still informs the user."""
        url = reverse("core:signup")
        response = client.post(
            url,
            {
                "email": "existing@example.com",
                "password1": "strongpassword123",
                "password2": "strongpassword123",
            },
        )
        content = response.content.decode()
        # The generic non-disclosing message introduced by this fix:
        assert "cannot be used" in content.lower()

    def test_unknown_email_rejected_yields_same_structure(self, client):
        """An unknown email with mismatched passwords also re-renders the form
        without confirming or denying account existence."""
        url = reverse("core:signup")
        response = client.post(
            url,
            {
                "email": "newuser@example.com",
                "password1": "strongpassword123",
                "password2": "differentpassword",
            },
        )
        assert response.status_code == 200
        # The "already exists" phrase must never appear.
        assert "already exists" not in response.content.decode().lower()


# ---------------------------------------------------------------------------
# Finding 6b — org_setup must not reveal account existence
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrgSetupEnumeration:
    """org_setup view must not distinguish between 'existing user, wrong password'
    and 'new user, missing fields' in any externally observable way."""

    @pytest.fixture
    def org_with_token(self, org_admin):
        """Organisation with an unconsumed setup token."""
        import uuid

        o = Organization.objects.create(
            name="Setup Org",
            owner=org_admin,
            setup_token=str(uuid.uuid4()),
        )
        return o

    def test_wrong_password_for_known_email_uses_generic_message(
        self, client, existing_user, org_with_token
    ):
        """An existing user's email with the wrong password must not produce
        a message that confirms the account exists."""
        url = reverse("core:org_setup", args=[org_with_token.setup_token])
        response = client.post(
            url,
            {
                "email": "existing@example.com",
                "password": "wrong-password",
                "accept_terms": "on",
            },
        )
        content = response.content.decode()

        # Forbidden phrasing that confirms account existence:
        assert "already exists" not in content.lower()
        assert "an account with this email" not in content.lower()

    def test_wrong_password_for_known_email_shows_generic_error(
        self, client, existing_user, org_with_token
    ):
        """The generic error message must still be displayed so the response is
        not a silent failure."""
        url = reverse("core:org_setup", args=[org_with_token.setup_token])
        response = client.post(
            url,
            {
                "email": "existing@example.com",
                "password": "wrong-password",
                "accept_terms": "on",
            },
        )
        content = response.content.decode()
        # The uniform error message introduced by this fix:
        assert "invalid email or password" in content.lower()

    def test_template_never_exposes_existing_user_flag(
        self, client, existing_user, org_with_token
    ):
        """
        The template must never render the ``existing_user`` disclosure text
        regardless of whether the submitted email belongs to an existing account.
        """
        url = reverse("core:org_setup", args=[org_with_token.setup_token])
        response = client.post(
            url,
            {
                "email": "existing@example.com",
                "password": "wrong-password",
                "accept_terms": "on",
            },
        )
        content = response.content.decode()
        # Text that was previously rendered only when existing_user=True:
        assert "enter your password to link this organization" not in content.lower()
        assert "your existing password" not in content.lower()

    def test_timing_normalisation_dummy_hash_called_for_unknown_user(
        self, client, org_with_token
    ):
        """
        When the submitted email does not match any account the view must still
        call the password hasher (User().set_password) so that response timing
        is equivalent to the existing-user path (which runs authenticate()).

        This is a structural test: we mock ``User.set_password`` and verify it
        is invoked on the unknown-email path before any early return.
        """
        url = reverse("core:org_setup", args=[org_with_token.setup_token])

        target = "django.contrib.auth.base_user.AbstractBaseUser.set_password"
        with patch(target) as mock_set_password:
            client.post(
                url,
                {
                    # Unknown email — no account exists for this address.
                    "email": "no-such-user@example.com",
                    "password": "short",  # too short → early return after hash
                    "accept_terms": "on",
                },
            )

        # set_password must have been called at least once (the dummy-hash call
        # that normalises timing).
        mock_set_password.assert_called()


# ---------------------------------------------------------------------------
# Finding 6c — org_users: explicit error, not silent no-op
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrgUsersEnumeration:
    """POST org_users with action=add and an unknown email must return an
    explicit error rather than silently succeeding — the silence/success
    binary previously leaked account existence."""

    def test_add_unknown_email_returns_error_message(self, client, org_admin, org):
        client.force_login(org_admin)
        url = reverse("surveys:org_users", args=[org.id])
        response = client.post(
            url,
            {
                "action": "add",
                "email": "nosuchuser@example.com",
                "role": OrganizationMembership.Role.VIEWER,
            },
            follow=True,
        )
        content = response.content.decode()
        assert "no user found" in content.lower()

    def test_add_unknown_email_does_not_silently_succeed(self, client, org_admin, org):
        """No membership must be created when the email is unknown."""
        client.force_login(org_admin)
        url = reverse("surveys:org_users", args=[org.id])
        before = OrganizationMembership.objects.filter(organization=org).count()
        client.post(
            url,
            {
                "action": "add",
                "email": "nosuchuser@example.com",
                "role": OrganizationMembership.Role.VIEWER,
            },
        )
        after = OrganizationMembership.objects.filter(organization=org).count()
        assert after == before, "Membership was unexpectedly created for unknown email"

    def test_add_known_email_still_works(self, client, org_admin, org, existing_user):
        """The error path must not break the happy path for existing accounts."""
        client.force_login(org_admin)
        url = reverse("surveys:org_users", args=[org.id])
        response = client.post(
            url,
            {
                "action": "add",
                "email": existing_user.email,
                "role": OrganizationMembership.Role.VIEWER,
            },
            follow=True,
        )
        assert OrganizationMembership.objects.filter(
            organization=org, user=existing_user
        ).exists()
        content = response.content.decode()
        assert "added" in content.lower() or "updated" in content.lower()


# ---------------------------------------------------------------------------
# Finding 6c — survey_users: explicit error, not silent no-op
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSurveyUsersEnumeration:
    """POST survey_users with action=add and an unknown email must return an
    explicit error rather than a silent no-op."""

    def test_add_unknown_email_returns_error_message(self, client, org_admin, survey):
        client.force_login(org_admin)
        url = reverse("surveys:survey_users", kwargs={"slug": survey.slug})
        response = client.post(
            url,
            {
                "action": "add",
                "email": "nosuchuser@example.com",
                "role": SurveyMembership.Role.VIEWER,
            },
            follow=True,
        )
        content = response.content.decode()
        assert "no user found" in content.lower()

    def test_add_unknown_email_does_not_create_membership(
        self, client, org_admin, survey
    ):
        client.force_login(org_admin)
        url = reverse("surveys:survey_users", kwargs={"slug": survey.slug})
        before = SurveyMembership.objects.filter(survey=survey).count()
        client.post(
            url,
            {
                "action": "add",
                "email": "nosuchuser@example.com",
                "role": SurveyMembership.Role.VIEWER,
            },
        )
        after = SurveyMembership.objects.filter(survey=survey).count()
        assert after == before

    def test_add_known_email_still_works(
        self, client, org_admin, survey, existing_user
    ):
        """The error path for unknown emails must not break the happy path.
        Tier limit checks are mocked here — they are tested separately."""
        client.force_login(org_admin)
        url = reverse("surveys:survey_users", kwargs={"slug": survey.slug})
        with patch(
            "checktick_app.core.tier_limits.check_collaboration_limit",
            return_value=(True, ""),
        ), patch(
            "checktick_app.core.tier_limits.check_collaborators_per_survey_limit",
            return_value=(True, ""),
        ):
            response = client.post(
                url,
                {
                    "action": "add",
                    "email": existing_user.email,
                    "role": SurveyMembership.Role.VIEWER,
                },
                follow=True,
            )
        assert SurveyMembership.objects.filter(
            survey=survey, user=existing_user
        ).exists()
        content = response.content.decode()
        assert "added" in content.lower() or "updated" in content.lower()


# ---------------------------------------------------------------------------
# Brute-force lockout configuration
# ---------------------------------------------------------------------------


class TestAxesLockoutConfiguration:
    """Verify that AXES_LOCKOUT_PARAMETERS is structured to prevent IP-rotation
    bypass of per-account lockouts."""

    def test_lockout_parameters_is_list_of_lists(self):
        """
        Users authenticate with their email address, submitted under the form
        field named 'username' (Django's AuthenticationForm convention).  Axes
        tracks lockouts using that field value, so 'username' in axes terms
        means the user's email address in this application.

        A flat list ``["username", "ip_address"]`` locks only on the
        *combination*, letting an attacker rotate IPs to keep targeting the same
        email address indefinitely.

        The correct form ``[["username"], ["ip_address"]]`` tracks each
        dimension independently, so hitting the limit on either one locks out.
        """
        params = settings.AXES_LOCKOUT_PARAMETERS
        assert isinstance(params, list), "AXES_LOCKOUT_PARAMETERS must be a list"
        for item in params:
            assert isinstance(item, list), (
                f"AXES_LOCKOUT_PARAMETERS items must be lists (got {type(item).__name__!r}: {item!r}). "
                "A flat list locks only on the combination; use a list-of-lists to lock independently."
            )

    def test_lockout_tracks_email_address_independently(self):
        """The email address is submitted under the 'username' form field
        (required by Django's AuthenticationForm).  It must appear as a
        standalone axes tracking dimension so that IP rotation cannot bypass
        a per-account lockout."""
        params = settings.AXES_LOCKOUT_PARAMETERS
        standalone_keys = {frozenset(item) for item in params if isinstance(item, list)}
        assert frozenset(["username"]) in standalone_keys, (
            "AXES_LOCKOUT_PARAMETERS must include ['username'] as a standalone "
            "dimension.  In this app 'username' holds the email address; "
            "locking by it independently prevents IP-rotation bypass."
        )

    def test_lockout_tracks_ip_independently(self):
        """IP address must appear as a standalone dimension to rate-limit
        credential-stuffing targeting many email addresses from one source."""
        params = settings.AXES_LOCKOUT_PARAMETERS
        standalone_keys = {frozenset(item) for item in params if isinstance(item, list)}
        assert frozenset(["ip_address"]) in standalone_keys, (
            "AXES_LOCKOUT_PARAMETERS must include ['ip_address'] as a standalone "
            "dimension to rate-limit credential-stuffing from a single IP."
        )
