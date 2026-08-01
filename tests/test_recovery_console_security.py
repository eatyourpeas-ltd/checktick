"""
Security tests for the Platform Recovery Console (F6 — August 2026 security review).

The documented ethical-recovery model requires 3 of 4 Shamir custodian shares to
reconstruct the platform custodian component before a survey KEK can be recovered
from Vault. The only intended execution path is the
`execute_platform_recovery` management command, which collects the shares on a
secure terminal and calls `shamir.reconstruct_secret`.

These tests verify that the web recovery console cannot bypass that control:

1. The `recovery_execute` web endpoint must NOT exist — there is no URL or
   view. Execution is CLI-only via the `execute_platform_recovery` management
   command.
2. `RecoveryRequest.execute_recovery` must NOT read the custodian component from
   `settings.PLATFORM_CUSTODIAN_COMPONENT`. The model method must require the
   custodian component as an explicit argument (or be removed entirely).
3. The `PLATFORM_CUSTODIAN_COMPONENT` setting must not exist in the codebase, so
   that any deploy that sets the env var fails loudly instead of silently
   re-enabling single-party decryption.
"""

import inspect

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.surveys.models import RecoveryRequest, Survey

User = get_user_model()

TEST_PASSWORD = "x"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="superadmin",
        email="superadmin@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def target_user(db):
    return User.objects.create_user(
        username="target",
        email="target@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def primary_approver(db):
    return User.objects.create_user(
        username="primary",
        email="primary@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def secondary_approver(db):
    return User.objects.create_user(
        username="secondary",
        email="secondary@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def ready_recovery_request(target_user, primary_approver, secondary_approver):
    """A RecoveryRequest that has passed dual approval + time delay and is
    READY_FOR_EXECUTION — exactly the state the web console used to act on."""
    survey = Survey.objects.create(
        name="Recovery Test Survey",
        slug="recovery-test-survey",
        owner=target_user,
    )

    rr = RecoveryRequest.objects.create(
        user=target_user,
        survey=survey,
        status=RecoveryRequest.Status.READY_FOR_EXECUTION,
        primary_approver=primary_approver,
        secondary_approver=secondary_approver,
        time_delay_hours=0,
    )
    return rr


# ---------------------------------------------------------------------------
# 1. The web execute view must not execute recovery
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecoveryExecuteViewDoesNotBypassCustodianControl:
    """F6: the web recovery console must not be a single-party decryption
    primitive. Execution must go through the management command."""

    def test_execute_route_removed(self, client, superuser, ready_recovery_request):
        """The web execution endpoint must not exist at all — there is no
        `recovery_execute` URL or view. Execution is CLI-only (F6)."""
        from django.urls import NoReverseMatch

        rr = ready_recovery_request

        # The URL name must be gone.
        with pytest.raises(NoReverseMatch):
            reverse("surveys:recovery_execute", kwargs={"request_id": rr.id})

        # A direct POST to the old path must 404, not silently execute.
        client.force_login(superuser)
        response = client.post(
            f"/surveys/recovery/{rr.id}/execute/",
            data={
                "new_password": "NewStrongPass!234",
                "confirm_password": "NewStrongPass!234",
            },
        )
        assert response.status_code == 404, (
            "The /recovery/<id>/execute/ route still resolves — it must be "
            "removed so the web console cannot execute recovery"
        )

        # The request must remain ready (not completed) — no silent execution.
        rr.refresh_from_db()
        assert rr.status == RecoveryRequest.Status.READY_FOR_EXECUTION
        assert rr.executed_by is None
        assert rr.completed_at is None

    def test_detail_page_no_execute_button_or_modal(
        self, client, superuser, ready_recovery_request
    ):
        """The recovery detail page must not render an "Execute Recovery" button
        or the password-entry modal — execution is CLI-only (F6)."""
        rr = ready_recovery_request
        client.force_login(superuser)

        url = reverse("surveys:recovery_detail", kwargs={"request_id": rr.id})
        response = client.get(url)

        assert response.status_code == 200
        body = response.content.decode()

        # The old execute button / modal must be gone.
        assert "execute_modal" not in body, (
            "recovery_detail.html still renders the execute_modal dialog — "
            "the web console must not present an execution UI"
        )
        assert 'name="new_password"' not in body, (
            "recovery_detail.html still renders a new_password form field — "
            "execution must not be possible from the web console"
        )

        # The page must instead surface the CLI guidance for a ready request.
        assert "execute_platform_recovery" in body, (
            "recovery_detail.html must show the execute_platform_recovery "
            "management command for ready-for-execution requests"
        )
        assert rr.request_code in body, (
            "The CLI guidance must include the request code so the operator "
            "can copy-paste the command"
        )


# ---------------------------------------------------------------------------
# 2. The model method must not read the custodian component from settings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecuteRecoveryDoesNotReadCustodianFromSettings:
    """F6: RecoveryRequest.execute_recovery must not pull the custodian
    component from settings. The custodian component must come from
    reconstructed Shamir shares supplied by the caller."""

    def test_execute_recovery_signature_requires_custodian_component(self):
        """The model method must accept the custodian component as an explicit
        argument — it must not have a code path that reads it from settings."""
        sig = inspect.signature(RecoveryRequest.execute_recovery)
        params = sig.parameters

        # `admin` and `new_password` are the original args. The fix must add an
        # explicit `custodian_component` parameter (no default) so callers are
        # forced to supply reconstructed shares.
        assert "custodian_component" in params, (
            "RecoveryRequest.execute_recovery must accept an explicit "
            "custodian_component argument"
        )
        assert params["custodian_component"].default is inspect.Parameter.empty, (
            "custodian_component must be a required argument — it must not "
            "default to reading from settings"
        )

    def test_execute_recovery_source_does_not_read_settings_custodian(self):
        """The body of execute_recovery must not reference
        settings.PLATFORM_CUSTODIAN_COMPONENT."""
        source = inspect.getsource(RecoveryRequest.execute_recovery)
        assert "PLATFORM_CUSTODIAN_COMPONENT" not in source, (
            "RecoveryRequest.execute_recovery must not reference "
            "settings.PLATFORM_CUSTODIAN_COMPONENT — the custodian component "
            "must be supplied by the caller from reconstructed Shamir shares"
        )


# ---------------------------------------------------------------------------
# 3. The PLATFORM_CUSTODIAN_COMPONENT setting must not exist
# ---------------------------------------------------------------------------


class TestPlatformCustodianComponentSettingRemoved:
    """F6: the setting must be removed from the codebase entirely so that any
    deploy that sets the env var fails loudly instead of silently re-enabling
    single-party decryption."""

    def test_setting_not_defined_in_settings_module(self):
        from django.conf import settings

        assert not hasattr(settings, "PLATFORM_CUSTODIAN_COMPONENT"), (
            "settings.PLATFORM_CUSTODIAN_COMPONENT must not exist — the "
            "custodian component must only ever come from reconstructed Shamir "
            "shares via the execute_platform_recovery management command"
        )

    def test_no_code_references_the_setting(self):
        """No application code should reference PLATFORM_CUSTODIAN_COMPONENT
        as a settings attribute."""
        import checktick_app.surveys.models as models_module
        import checktick_app.surveys.views as views_module

        for mod in (models_module, views_module):
            source = inspect.getsource(mod)
            assert "PLATFORM_CUSTODIAN_COMPONENT" not in source, (
                f"{mod.__name__} references PLATFORM_CUSTODIAN_COMPONENT — "
                "the setting must not be used anywhere in application code"
            )
