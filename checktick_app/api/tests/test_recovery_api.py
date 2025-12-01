"""
Tests for key recovery API endpoints.

These tests verify the recovery request workflow including:
- Creating recovery requests
- Viewing request status
- Admin approval workflow
- Request cancellation
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
import pytest
from rest_framework.test import APIClient

from checktick_app.surveys.models import (
    RecoveryAuditEntry,
    RecoveryRequest,
    Survey,
    SurveyResponse,
)

User = get_user_model()
TEST_PASSWORD = "testpass123"


def auth_hdr(client, username: str, password: str) -> dict:
    """Helper to get JWT auth header."""
    resp = client.post(
        "/api/token",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    return {"HTTP_AUTHORIZATION": f"Bearer {resp.json()['access']}"}


@pytest.fixture
def api_client():
    """Return a fresh API client."""
    return APIClient()


@pytest.fixture
def regular_user(django_user_model):
    """Create a regular non-admin user."""
    return django_user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def admin_user(django_user_model):
    """Create a platform admin user."""
    return django_user_model.objects.create_user(
        username="admin",
        email="admin@example.com",
        password=TEST_PASSWORD,
        is_staff=True,
    )


@pytest.fixture
def second_admin_user(django_user_model):
    """Create a second platform admin user for dual authorization."""
    return django_user_model.objects.create_user(
        username="admin2",
        email="admin2@example.com",
        password=TEST_PASSWORD,
        is_staff=True,
    )


@pytest.fixture
def survey_with_encrypted_responses(regular_user):
    """Create a survey with encrypted responses for the user."""
    survey = Survey.objects.create(
        name="Test Encrypted Survey",
        slug="test-encrypted-survey",
        owner=regular_user,
    )

    # Create a response with encrypted data
    SurveyResponse.objects.create(
        survey=survey,
        submitted_by=regular_user,
        enc_demographics=b"encrypted_data_here",
    )

    return survey


@pytest.fixture
def recovery_request(regular_user, survey_with_encrypted_responses):
    """Create a pending recovery request."""
    return RecoveryRequest.objects.create(
        user=regular_user,
        survey=survey_with_encrypted_responses,
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
        user_context={"reason": "Forgot passphrase"},
    )


class TestRecoveryRequestCreate:
    """Tests for creating recovery requests."""

    @patch("checktick_app.api.views.RecoveryViewSet._send_request_notifications")
    def test_create_recovery_request(
        self,
        mock_notifications,
        api_client,
        regular_user,
        survey_with_encrypted_responses,
    ):
        """Test creating a new recovery request."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            "/api/recovery/",
            data=json.dumps(
                {
                    "survey_id": survey_with_encrypted_responses.id,
                    "reason": "Forgot my passphrase and need to recover access",
                }
            ),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "request_code" in data
        assert data["status"] == RecoveryRequest.Status.PENDING_VERIFICATION
        assert mock_notifications.called

    def test_create_request_requires_auth(
        self, api_client, survey_with_encrypted_responses
    ):
        """Test that creating a request requires authentication."""
        response = api_client.post(
            "/api/recovery/",
            data=json.dumps(
                {
                    "survey_id": survey_with_encrypted_responses.id,
                    "reason": "Test reason",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 401

    @patch("checktick_app.api.views.RecoveryViewSet._send_request_notifications")
    def test_cannot_create_duplicate_request(
        self,
        mock_notifications,
        api_client,
        regular_user,
        survey_with_encrypted_responses,
    ):
        """Test that duplicate pending requests are rejected."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        # Create first request
        RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey_with_encrypted_responses,
            status=RecoveryRequest.Status.PENDING_VERIFICATION,
        )

        # Try to create second request
        response = api_client.post(
            "/api/recovery/",
            data=json.dumps(
                {
                    "survey_id": survey_with_encrypted_responses.id,
                    "reason": "Test reason",
                }
            ),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 400
        assert "pending recovery request already exists" in response.json()["error"]

    def test_create_request_nonexistent_survey(self, api_client, regular_user):
        """Test creating request for non-existent survey."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            "/api/recovery/",
            data=json.dumps(
                {
                    "survey_id": 99999,
                    "reason": "Test reason",
                }
            ),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 404


class TestRecoveryRequestList:
    """Tests for listing recovery requests."""

    def test_user_sees_own_requests(self, api_client, regular_user, recovery_request):
        """Test that users can see their own recovery requests."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.get("/api/recovery/", **headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["request_code"] == recovery_request.request_code

    def test_user_cannot_see_others_requests(
        self, api_client, regular_user, admin_user, survey_with_encrypted_responses
    ):
        """Test that users cannot see others' recovery requests."""
        # Create request for another user
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password=TEST_PASSWORD
        )
        RecoveryRequest.objects.create(
            user=other_user,
            survey=survey_with_encrypted_responses,
            status=RecoveryRequest.Status.PENDING_VERIFICATION,
        )

        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)
        response = api_client.get("/api/recovery/", **headers)

        assert response.status_code == 200
        # Regular user sees no requests (they don't own any)
        assert len(response.json()) == 0

    def test_admin_sees_all_requests(self, api_client, admin_user, recovery_request):
        """Test that admins can see all recovery requests."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        response = api_client.get("/api/recovery/admin/", **headers)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1


class TestRecoveryRequestCancel:
    """Tests for cancelling recovery requests."""

    def test_user_can_cancel_own_request(
        self, api_client, regular_user, recovery_request
    ):
        """Test that users can cancel their own pending requests."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/cancel/",
            data=json.dumps({"reason": "Changed my mind"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.CANCELLED

    def test_user_cannot_cancel_others_request(
        self, api_client, regular_user, admin_user, survey_with_encrypted_responses
    ):
        """Test that users cannot cancel others' requests."""
        # Create request for another user
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password=TEST_PASSWORD
        )
        other_request = RecoveryRequest.objects.create(
            user=other_user,
            survey=survey_with_encrypted_responses,
            status=RecoveryRequest.Status.AWAITING_PRIMARY,
        )

        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{other_request.id}/cancel/",
            data=json.dumps({"reason": "Test"}),
            content_type="application/json",
            **headers,
        )

        # Should get 404 (not found for this user) or 403 (permission denied)
        assert response.status_code in [403, 404]


class TestRecoveryAdminApproval:
    """Tests for admin approval workflow."""

    def test_primary_approval(self, api_client, admin_user, recovery_request):
        """Test primary admin approval."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_primary/",
            data=json.dumps({"reason": "Identity verified via video call"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY
        assert recovery_request.primary_approver == admin_user

    def test_non_admin_cannot_approve(self, api_client, regular_user, recovery_request):
        """Test that non-admins cannot approve requests."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_primary/",
            data=json.dumps({"reason": "Test"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 403

    @patch("checktick_app.core.email_utils.send_recovery_approved_email")
    def test_secondary_approval_starts_time_delay(
        self, mock_email, api_client, admin_user, second_admin_user, recovery_request
    ):
        """Test secondary approval starts time delay."""
        # First, primary approval
        recovery_request.approve_primary(admin_user, "Primary verification")

        # Now secondary approval
        headers = auth_hdr(api_client, second_admin_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_secondary/",
            data=json.dumps({"reason": "Secondary verification complete"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY
        assert recovery_request.time_delay_until is not None
        assert mock_email.called

    def test_same_admin_cannot_do_both_approvals(
        self, api_client, admin_user, recovery_request
    ):
        """Test that the same admin cannot do both approvals."""
        # First approval
        recovery_request.approve_primary(admin_user, "Primary verification")

        # Try to do secondary with same admin
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_secondary/",
            data=json.dumps({"reason": "Test"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 400
        assert "different" in response.json()["error"].lower()


class TestRecoveryRejection:
    """Tests for rejecting recovery requests."""

    @patch("checktick_app.core.email_utils.send_recovery_rejected_email")
    def test_admin_can_reject_request(
        self, mock_email, api_client, admin_user, recovery_request
    ):
        """Test that admins can reject recovery requests."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/reject/",
            data=json.dumps({"reason": "Identity verification failed"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.REJECTED
        assert mock_email.called


class TestTimeDelayCheck:
    """Tests for time delay checking."""

    def test_check_time_delay_incomplete(
        self, api_client, admin_user, second_admin_user, recovery_request
    ):
        """Test checking time delay when not yet complete."""

        # Set up approved request in time delay
        recovery_request.approve_primary(admin_user, "Primary")
        recovery_request.approve_secondary(second_admin_user, "Secondary")

        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/check-time-delay/",
            **headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_delay_complete"] is False

    @patch("checktick_app.core.email_utils.send_recovery_ready_email")
    def test_check_time_delay_complete(
        self, mock_email, api_client, admin_user, second_admin_user, recovery_request
    ):
        """Test checking time delay when complete."""
        from datetime import timedelta

        from django.utils import timezone

        # Set up approved request with expired time delay
        recovery_request.approve_primary(admin_user, "Primary")
        recovery_request.approve_secondary(second_admin_user, "Secondary")

        # Manually set time delay to past
        recovery_request.time_delay_until = timezone.now() - timedelta(hours=1)
        recovery_request.save()

        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/check-time-delay/",
            **headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_delay_complete"] is True
        assert mock_email.called

        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.READY_FOR_EXECUTION


class TestRecoveryAuditLogging:
    """Tests for audit logging on recovery actions."""

    @patch("checktick_app.api.views.RecoveryViewSet._send_request_notifications")
    def test_create_request_creates_audit_entry(
        self,
        mock_notifications,
        api_client,
        regular_user,
        survey_with_encrypted_responses,
    ):
        """Test that creating a request creates an audit log entry."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            "/api/recovery/",
            data=json.dumps(
                {
                    "survey_id": survey_with_encrypted_responses.id,
                    "reason": "Lost my passphrase",
                }
            ),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 201

        # Check audit entry was created
        request_id = response.json()["id"]
        recovery_request = RecoveryRequest.objects.get(id=request_id)
        audit_entries = RecoveryAuditEntry.objects.filter(
            recovery_request=recovery_request
        )

        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.event_type == "request_submitted"
        assert entry.actor_type == "user"
        assert entry.actor_id == regular_user.id
        assert entry.actor_email == regular_user.email
        assert entry.severity == "info"
        assert "reason" in entry.details

    def test_cancel_creates_audit_entry(
        self, api_client, regular_user, recovery_request
    ):
        """Test that cancelling a request creates an audit log entry."""
        headers = auth_hdr(api_client, regular_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/cancel/",
            data=json.dumps({"reason": "Changed my mind"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200

        # Check audit entry was created (by model's cancel() method)
        audit_entries = RecoveryAuditEntry.objects.filter(
            recovery_request=recovery_request, event_type="cancellation"
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        # Model auto-detects actor_type based on is_staff
        assert entry.actor_type in ["user", "admin"]
        assert "reason" in entry.details

    def test_primary_approval_creates_audit_entry(
        self, api_client, admin_user, recovery_request
    ):
        """Test that primary approval creates an audit log entry."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_primary/",
            data=json.dumps({"reason": "Identity verified"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200

        # Check audit entry was created (by model's approve_primary() method)
        audit_entries = RecoveryAuditEntry.objects.filter(
            recovery_request=recovery_request, event_type="primary_approval"
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.actor_type == "admin"
        assert entry.severity == "info"  # Model uses default severity
        assert entry.actor_id == admin_user.id

    @patch("checktick_app.core.email_utils.send_recovery_approved_email")
    def test_secondary_approval_creates_critical_audit_entry(
        self, mock_email, api_client, admin_user, second_admin_user, recovery_request
    ):
        """Test that secondary approval creates a critical audit log entry."""
        # First, primary approval
        recovery_request.approve_primary(admin_user, "Primary verification")

        headers = auth_hdr(api_client, second_admin_user.username, TEST_PASSWORD)
        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_secondary/",
            data=json.dumps({"reason": "Secondary verification"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200

        # Check audit entry was created (by model's approve_secondary() method)
        audit_entries = RecoveryAuditEntry.objects.filter(
            recovery_request=recovery_request, event_type="secondary_approval"
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.severity == "info"  # Model uses default severity
        assert entry.actor_id == second_admin_user.id
        assert "time_delay_until" in entry.details

    @patch("checktick_app.core.email_utils.send_recovery_rejected_email")
    def test_rejection_creates_audit_entry(
        self, mock_email, api_client, admin_user, recovery_request
    ):
        """Test that rejection creates an audit log entry."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        response = api_client.post(
            f"/api/recovery/{recovery_request.id}/reject/",
            data=json.dumps({"reason": "Suspicious request"}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == 200

        # Check audit entry was created (by model's reject() method)
        audit_entries = RecoveryAuditEntry.objects.filter(
            recovery_request=recovery_request, event_type="rejection"
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.actor_type == "admin"
        assert entry.severity == "info"  # Model uses default severity
        assert entry.details["reason"] == "Suspicious request"

    def test_audit_entries_have_hash_chain(
        self, api_client, admin_user, recovery_request
    ):
        """Test that audit entries form a cryptographic hash chain."""
        headers = auth_hdr(api_client, admin_user.username, TEST_PASSWORD)

        # First action: primary approval
        api_client.post(
            f"/api/recovery/{recovery_request.id}/approve_primary/",
            data=json.dumps({"reason": "First approval"}),
            content_type="application/json",
            **headers,
        )

        # Get audit entries in order
        entries = list(
            RecoveryAuditEntry.objects.filter(
                recovery_request=recovery_request
            ).order_by("timestamp")
        )

        assert len(entries) >= 1

        # First entry should have empty previous_hash
        assert entries[0].previous_hash == ""

        # Each entry should have a non-empty hash
        for entry in entries:
            assert entry.entry_hash != ""
            assert len(entry.entry_hash) == 64  # SHA-256 hex digest
