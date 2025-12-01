"""
Tests for the process_recovery_time_delays management command.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    RecoveryRequest,
    Survey,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def org_owner(db):
    """Organization owner user."""
    return User.objects.create_user(
        username="orgowner",
        email="orgowner@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def org_admin(db):
    """Organization admin user."""
    return User.objects.create_user(
        username="orgadmin",
        email="orgadmin@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def regular_user(db):
    """Regular user who owns surveys."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def organization(db, org_owner):
    """Test organization."""
    return Organization.objects.create(
        name="Test Organization",
        owner=org_owner,
    )


@pytest.fixture
def org_admin_membership(db, organization, org_admin):
    """Make org_admin an admin of the organization."""
    return OrganizationMembership.objects.create(
        organization=organization,
        user=org_admin,
        role=OrganizationMembership.Role.ADMIN,
    )


@pytest.fixture
def survey(db, regular_user, organization):
    """Survey owned by regular_user in organization."""
    return Survey.objects.create(
        name="Test Survey",
        slug="test-survey-main",
        owner=regular_user,
        organization=organization,
    )


@pytest.fixture
def expired_recovery_request(db, regular_user, survey, org_owner, org_admin):
    """Recovery request with expired time delay."""
    request = RecoveryRequest.objects.create(
        user=regular_user,
        survey=survey,
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
        time_delay_hours=24,
    )
    # Manually approve to get to IN_TIME_DELAY status
    request.approve_primary(admin=org_owner, reason="Approved")
    request.approve_secondary(admin=org_admin, reason="Approved")

    # Now backdate the time_delay_until to make it expired
    request.time_delay_until = timezone.now() - timedelta(hours=1)
    request.save(update_fields=["time_delay_until"])

    return request


@pytest.fixture
def active_recovery_request(db, regular_user, survey, org_owner, org_admin):
    """Recovery request with active (non-expired) time delay."""
    # Create a different survey for this request
    survey2 = Survey.objects.create(
        name="Test Survey 2",
        slug="test-survey-2-active",
        owner=regular_user,
        organization=survey.organization,
    )

    request = RecoveryRequest.objects.create(
        user=regular_user,
        survey=survey2,
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
        time_delay_hours=24,
    )
    # Manually approve to get to IN_TIME_DELAY status
    request.approve_primary(admin=org_owner, reason="Approved")
    request.approve_secondary(admin=org_admin, reason="Approved")

    # time_delay_until should still be in the future
    assert request.time_delay_until is not None
    assert request.time_delay_until > timezone.now()

    return request


@pytest.mark.django_db
class TestProcessRecoveryTimeDelays:
    """Tests for the process_recovery_time_delays command."""

    def test_processes_expired_request(self, expired_recovery_request):
        """Command processes requests with expired time delays."""
        out = StringIO()
        call_command("process_recovery_time_delays", "--verbose", stdout=out)

        expired_recovery_request.refresh_from_db()
        assert (
            expired_recovery_request.status
            == RecoveryRequest.Status.READY_FOR_EXECUTION
        )

        output = out.getvalue()
        assert "Found 1 recovery request" in output
        assert "Processed 1" in output

    def test_ignores_active_request(self, active_recovery_request):
        """Command ignores requests with non-expired time delays."""
        out = StringIO()
        call_command("process_recovery_time_delays", "--verbose", stdout=out)

        active_recovery_request.refresh_from_db()
        assert active_recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY

        output = out.getvalue()
        assert "No expired time delays found" in output

    def test_dry_run_does_not_modify(self, expired_recovery_request):
        """Dry run mode shows what would be done but doesn't modify."""
        out = StringIO()
        call_command(
            "process_recovery_time_delays", "--dry-run", "--verbose", stdout=out
        )

        expired_recovery_request.refresh_from_db()
        # Should still be IN_TIME_DELAY
        assert expired_recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY

        output = out.getvalue()
        assert "DRY RUN" in output
        assert "Would process 1" in output

    def test_processes_multiple_expired_requests(
        self, expired_recovery_request, regular_user, survey, org_owner, org_admin
    ):
        """Command processes multiple expired requests."""
        # Create second expired request
        survey2 = Survey.objects.create(
            name="Test Survey 3",
            slug="test-survey-3-multi",
            owner=regular_user,
            organization=survey.organization,
        )
        request2 = RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey2,
            status=RecoveryRequest.Status.AWAITING_PRIMARY,
            time_delay_hours=24,
        )
        request2.approve_primary(admin=org_owner, reason="Approved")
        request2.approve_secondary(admin=org_admin, reason="Approved")
        request2.time_delay_until = timezone.now() - timedelta(hours=2)
        request2.save(update_fields=["time_delay_until"])

        out = StringIO()
        call_command("process_recovery_time_delays", "--verbose", stdout=out)

        expired_recovery_request.refresh_from_db()
        request2.refresh_from_db()

        assert (
            expired_recovery_request.status
            == RecoveryRequest.Status.READY_FOR_EXECUTION
        )
        assert request2.status == RecoveryRequest.Status.READY_FOR_EXECUTION

        output = out.getvalue()
        assert "Found 2 recovery request" in output
        assert "Processed 2" in output

    def test_ignores_non_time_delay_statuses(self, regular_user, survey):
        """Command ignores requests not in IN_TIME_DELAY status."""
        # Create request in PENDING status
        pending_request = RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey,
            status=RecoveryRequest.Status.PENDING_VERIFICATION,
        )

        out = StringIO()
        call_command("process_recovery_time_delays", "--verbose", stdout=out)

        pending_request.refresh_from_db()
        assert pending_request.status == RecoveryRequest.Status.PENDING_VERIFICATION

        output = out.getvalue()
        assert "No expired time delays found" in output

    def test_creates_audit_entry(self, expired_recovery_request):
        """Processing creates an audit entry."""
        initial_count = expired_recovery_request.audit_entries.count()

        call_command("process_recovery_time_delays")

        expired_recovery_request.refresh_from_db()
        assert expired_recovery_request.audit_entries.count() > initial_count

        latest_entry = expired_recovery_request.audit_entries.order_by(
            "-timestamp"
        ).first()
        assert latest_entry.event_type == "time_delay_complete"

    @patch(
        "checktick_app.surveys.management.commands.process_recovery_time_delays.Command._send_ready_notification"
    )
    def test_sends_notification(self, mock_send, expired_recovery_request):
        """Processing sends notification email."""
        call_command("process_recovery_time_delays", "--verbose")

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == expired_recovery_request

    def test_handles_notification_error_gracefully(self, expired_recovery_request):
        """Command handles notification errors without failing."""
        with patch(
            "checktick_app.surveys.management.commands.process_recovery_time_delays.Command._send_ready_notification",
            side_effect=Exception("Email failed"),
        ):
            out = StringIO()
            # Should not raise
            call_command("process_recovery_time_delays", "--verbose", stdout=out)

            # Request should still be updated
            expired_recovery_request.refresh_from_db()
            assert (
                expired_recovery_request.status
                == RecoveryRequest.Status.READY_FOR_EXECUTION
            )

    def test_quiet_mode_minimal_output(self, expired_recovery_request):
        """Without verbose flag, output is minimal."""
        out = StringIO()
        call_command("process_recovery_time_delays", stdout=out)

        output = out.getvalue()
        # Should have summary but not detailed per-request output
        assert "Processed 1" in output
        assert "Processing:" not in output
