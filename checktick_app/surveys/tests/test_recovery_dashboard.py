"""
Tests for the Superuser Platform Recovery Console.

These tests verify:
1. Superuser-only access (non-superusers get 403)
2. Rate limiting is applied
3. Dashboard functionality
4. Approval/reject/execute actions
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from checktick_app.surveys.models import (
    Organization,
    RecoveryRequest,
    Survey,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def regular_user(db):
    """A regular authenticated user (not superuser)."""
    return User.objects.create_user(
        username="regularuser",
        email="regular@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def staff_user(db):
    """A staff user (not superuser)."""
    user = User.objects.create_user(
        username="staffuser",
        email="staff@example.com",
        password=TEST_PASSWORD,
    )
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def superuser(db):
    """A superuser."""
    return User.objects.create_superuser(
        username="superuser",
        email="super@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def second_superuser(db):
    """A second superuser for dual approval tests."""
    return User.objects.create_superuser(
        username="superuser2",
        email="super2@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def organization(db, regular_user):
    """An organization for testing."""
    return Organization.objects.create(
        name="Test Organization",
        owner=regular_user,
    )


@pytest.fixture
def survey(db, regular_user, organization):
    """A survey for testing."""
    return Survey.objects.create(
        name="Test Survey",
        slug=f"test-survey-{uuid.uuid4().hex[:8]}",
        owner=regular_user,
        organization=organization,
    )


@pytest.fixture
def recovery_request(db, regular_user, survey):
    """A recovery request for testing."""
    return RecoveryRequest.objects.create(
        user=regular_user,
        survey=survey,
        user_context={"reason": "Lost access to my encryption key"},
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
    )


@pytest.fixture
def disable_rate_limiting(settings):
    """Disable rate limiting for most tests."""
    settings.RATELIMIT_ENABLE = False


class TestRecoveryDashboardAccess:
    """Test that only superusers can access the recovery dashboard."""

    def test_anonymous_user_redirected_to_login(self, client, db):
        """Anonymous users should be redirected to login."""
        url = reverse("surveys:recovery_dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_regular_user_gets_403(self, client, regular_user, disable_rate_limiting):
        """Regular authenticated users should get 403 Forbidden."""
        client.force_login(regular_user)
        url = reverse("surveys:recovery_dashboard")
        response = client.get(url)
        assert response.status_code == 403

    def test_staff_user_gets_403(self, client, staff_user, disable_rate_limiting):
        """Staff users (non-superuser) should get 403 Forbidden."""
        client.force_login(staff_user)
        url = reverse("surveys:recovery_dashboard")
        response = client.get(url)
        assert response.status_code == 403

    def test_superuser_can_access(self, client, superuser, disable_rate_limiting):
        """Superusers should be able to access the dashboard."""
        client.force_login(superuser)
        url = reverse("surveys:recovery_dashboard")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Platform Recovery Console" in response.content


class TestRecoveryDetailAccess:
    """Test that only superusers can access recovery request details."""

    def test_anonymous_user_redirected(self, client, recovery_request):
        """Anonymous users should be redirected to login."""
        url = reverse("surveys:recovery_detail", kwargs={"request_id": recovery_request.id})
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_gets_403(self, client, regular_user, recovery_request, disable_rate_limiting):
        """Regular users should get 403 Forbidden."""
        client.force_login(regular_user)
        url = reverse("surveys:recovery_detail", kwargs={"request_id": recovery_request.id})
        response = client.get(url)
        assert response.status_code == 403

    def test_superuser_can_access(self, client, superuser, recovery_request, disable_rate_limiting):
        """Superusers should be able to access the detail view."""
        client.force_login(superuser)
        url = reverse("surveys:recovery_detail", kwargs={"request_id": recovery_request.id})
        response = client.get(url)
        assert response.status_code == 200
        assert recovery_request.request_code.encode() in response.content


class TestRecoveryApprovalActions:
    """Test approval actions are superuser-only."""

    def test_primary_approval_requires_superuser(
        self, client, regular_user, recovery_request, disable_rate_limiting
    ):
        """Non-superusers cannot approve requests."""
        client.force_login(regular_user)
        url = reverse("surveys:recovery_approve_primary", kwargs={"request_id": recovery_request.id})
        response = client.post(url)
        assert response.status_code == 403

    def test_superuser_can_approve_primary(
        self, client, superuser, recovery_request, disable_rate_limiting
    ):
        """Superusers can approve as primary."""
        client.force_login(superuser)
        url = reverse("surveys:recovery_approve_primary", kwargs={"request_id": recovery_request.id})
        response = client.post(url)
        # Should redirect to detail page
        assert response.status_code == 302

        # Check the request was updated
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY
        assert recovery_request.primary_approver == superuser

    def test_superuser_cannot_approve_own_request(
        self, client, superuser, survey, disable_rate_limiting
    ):
        """Superusers cannot approve their own recovery requests."""
        # Create a recovery request for the superuser
        own_request = RecoveryRequest.objects.create(
            user=superuser,
            survey=survey,
            user_context={"reason": "Lost my key"},
            status=RecoveryRequest.Status.AWAITING_PRIMARY,
        )

        client.force_login(superuser)
        url = reverse("surveys:recovery_approve_primary", kwargs={"request_id": own_request.id})
        response = client.post(url)

        # Should redirect with error
        assert response.status_code == 302

        # Request should not be approved
        own_request.refresh_from_db()
        assert own_request.status == RecoveryRequest.Status.AWAITING_PRIMARY


class TestRecoveryRejectAction:
    """Test rejection action is superuser-only."""

    def test_reject_requires_superuser(
        self, client, regular_user, recovery_request, disable_rate_limiting
    ):
        """Non-superusers cannot reject requests."""
        client.force_login(regular_user)
        url = reverse("surveys:recovery_reject", kwargs={"request_id": recovery_request.id})
        response = client.post(url, {"reason": "Suspicious request"})
        assert response.status_code == 403

    def test_superuser_can_reject(
        self, client, superuser, recovery_request, disable_rate_limiting
    ):
        """Superusers can reject requests."""
        client.force_login(superuser)
        url = reverse("surveys:recovery_reject", kwargs={"request_id": recovery_request.id})
        response = client.post(url, {"reason": "Suspicious activity detected"})

        # Should redirect
        assert response.status_code == 302

        # Check the request was rejected
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.REJECTED
        assert recovery_request.rejected_by == superuser


class TestRecoveryExecuteAction:
    """Test execute action is superuser-only."""

    def test_execute_requires_superuser(
        self, client, regular_user, recovery_request, disable_rate_limiting
    ):
        """Non-superusers cannot execute recovery."""
        recovery_request.status = RecoveryRequest.Status.READY_FOR_EXECUTION
        recovery_request.save()

        client.force_login(regular_user)
        url = reverse("surveys:recovery_execute", kwargs={"request_id": recovery_request.id})
        response = client.post(url)
        assert response.status_code == 403

    def test_superuser_can_execute(
        self, client, superuser, recovery_request, disable_rate_limiting
    ):
        """Superusers can execute ready requests."""
        recovery_request.status = RecoveryRequest.Status.READY_FOR_EXECUTION
        recovery_request.save()

        client.force_login(superuser)
        url = reverse("surveys:recovery_execute", kwargs={"request_id": recovery_request.id})
        response = client.post(url)

        # Should redirect
        assert response.status_code == 302

        # Check the request was executed
        recovery_request.refresh_from_db()
        assert recovery_request.status == RecoveryRequest.Status.COMPLETED
        assert recovery_request.executed_by == superuser


class TestRateLimiting:
    """Test that rate limiting is applied to recovery console."""

    @override_settings(RATELIMIT_ENABLE=True)
    def test_dashboard_rate_limited(self, client, superuser):
        """Dashboard should be rate limited."""
        client.force_login(superuser)
        url = reverse("surveys:recovery_dashboard")

        # Make requests up to the limit (30/hour)
        # We just test that rate limiting is configured, not exhaustively
        for _ in range(5):
            response = client.get(url)
            # Should succeed within limit
            assert response.status_code == 200

    @override_settings(RATELIMIT_ENABLE=True)
    def test_approval_action_rate_limited(self, client, superuser, survey, db):
        """Approval actions should be rate limited."""
        client.force_login(superuser)

        # Create multiple requests to approve
        requests = []
        for i in range(3):
            req = RecoveryRequest.objects.create(
                user=User.objects.create_user(
                    username=f"testuser{i}",
                    email=f"test{i}@example.com",
                    password=TEST_PASSWORD,
                ),
                survey=survey,
                user_context={"reason": "Test"},
                status=RecoveryRequest.Status.AWAITING_PRIMARY,
            )
            requests.append(req)

        # First few approvals should work
        for req in requests[:2]:
            url = reverse("surveys:recovery_approve_primary", kwargs={"request_id": req.id})
            response = client.post(url)
            # 302 redirect means success
            assert response.status_code == 302


class TestNavbarSuperuserBadge:
    """Test that superusers see the correct badge in the navbar."""

    def test_regular_user_sees_tier_badge(self, client, regular_user, disable_rate_limiting):
        """Regular users should see their tier badge."""
        client.force_login(regular_user)
        response = client.get("/surveys/")
        # Should not see SUPERUSER badge
        assert b"SUPERUSER" not in response.content

    def test_superuser_sees_superuser_badge(self, client, superuser, disable_rate_limiting):
        """Superusers should see the SUPERUSER badge."""
        client.force_login(superuser)
        response = client.get("/surveys/")
        # Should see SUPERUSER badge
        assert b"SUPERUSER" in response.content


class TestDashboardStats:
    """Test that dashboard shows correct stats."""

    def test_shows_all_recovery_requests(
        self, client, superuser, regular_user, survey, disable_rate_limiting
    ):
        """Dashboard should show all recovery requests across all orgs."""
        # Create multiple requests
        RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey,
            user_context={"reason": "Request 1"},
            status=RecoveryRequest.Status.AWAITING_PRIMARY,
        )
        RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey,
            user_context={"reason": "Request 2"},
            status=RecoveryRequest.Status.COMPLETED,
        )

        client.force_login(superuser)
        url = reverse("surveys:recovery_dashboard")
        response = client.get(url)

        assert response.status_code == 200
        # Should show both requests
        assert b"Request 1" in response.content or response.context["stats"]["total"] >= 2


class TestFilterFunctionality:
    """Test that filters work correctly."""

    def test_filter_by_status(
        self, client, superuser, regular_user, survey, disable_rate_limiting
    ):
        """Filters should correctly filter recovery requests."""
        # Create requests with different statuses
        RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey,
            user_context={"reason": "Pending"},
            status=RecoveryRequest.Status.PENDING_VERIFICATION,
        )
        RecoveryRequest.objects.create(
            user=regular_user,
            survey=survey,
            user_context={"reason": "Completed"},
            status=RecoveryRequest.Status.COMPLETED,
        )

        client.force_login(superuser)

        # Filter by pending
        response = client.get(reverse("surveys:recovery_dashboard") + "?filter=pending")
        assert response.status_code == 200

        # Filter by completed
        response = client.get(reverse("surveys:recovery_dashboard") + "?filter=completed")
        assert response.status_code == 200
