"""
Tests for the Admin Recovery Dashboard (Organization/Team Admins).

These tests verify:
1. Org admin access and scoping
2. Team admin/owner access and scoping
3. Rate limiting is applied
4. Dashboard functionality
5. Approval/reject actions with proper scoping
"""

import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    RecoveryRequest,
    Survey,
    Team,
)

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def regular_user(db):
    """A regular authenticated user."""
    return User.objects.create_user(
        username="regularuser",
        email="regular@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def org_owner(db):
    """An organization owner."""
    return User.objects.create_user(
        username="orgowner",
        email="orgowner@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def org_admin(db):
    """An organization admin (not owner)."""
    return User.objects.create_user(
        username="orgadmin",
        email="orgadmin@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def team_owner(db):
    """A team owner."""
    return User.objects.create_user(
        username="teamowner",
        email="teamowner@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def organization(db, org_owner):
    """An organization for testing."""
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
def standalone_team(db, team_owner):
    """A standalone team (no organization)."""
    return Team.objects.create(
        name="Standalone Team",
        owner=team_owner,
    )


@pytest.fixture
def org_survey(db, regular_user, organization):
    """A survey belonging to an organization."""
    return Survey.objects.create(
        name="Org Survey",
        slug=f"org-survey-{uuid.uuid4().hex[:8]}",
        owner=regular_user,
        organization=organization,
    )


@pytest.fixture
def team_survey(db, regular_user, standalone_team):
    """A survey belonging to a standalone team."""
    return Survey.objects.create(
        name="Team Survey",
        slug=f"team-survey-{uuid.uuid4().hex[:8]}",
        owner=regular_user,
        team=standalone_team,
    )


@pytest.fixture
def org_recovery_request(db, regular_user, org_survey):
    """A recovery request for an org survey."""
    return RecoveryRequest.objects.create(
        user=regular_user,
        survey=org_survey,
        user_context={"reason": "Lost org key"},
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
    )


@pytest.fixture
def team_recovery_request(db, regular_user, team_survey):
    """A recovery request for a team survey."""
    return RecoveryRequest.objects.create(
        user=regular_user,
        survey=team_survey,
        user_context={"reason": "Lost team key"},
        status=RecoveryRequest.Status.AWAITING_PRIMARY,
    )


@pytest.fixture
def disable_rate_limiting(settings):
    """Disable rate limiting for tests."""
    settings.RATELIMIT_ENABLE = False


class TestOrgAdminDashboardAccess:
    """Test that org admins can access their scoped dashboard."""

    def test_regular_user_without_context_redirected(
        self, client, regular_user, disable_rate_limiting
    ):
        """Regular users without org/team context are redirected."""
        client.force_login(regular_user)
        url = reverse("surveys:admin_recovery_dashboard")
        response = client.get(url)
        assert response.status_code == 302  # Redirected to surveys

    def test_org_owner_can_access_dashboard(
        self,
        client,
        org_owner,
        organization,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Org owner can access their org's recovery dashboard."""
        client.force_login(org_owner)
        url = reverse("surveys:admin_recovery_dashboard") + f"?org={organization.id}"
        response = client.get(url)
        assert response.status_code == 200
        assert b"Test Organization Recovery Dashboard" in response.content

    def test_org_admin_can_access_dashboard(
        self,
        client,
        org_admin,
        organization,
        org_admin_membership,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Org admin can access their org's recovery dashboard."""
        client.force_login(org_admin)
        url = reverse("surveys:admin_recovery_dashboard") + f"?org={organization.id}"
        response = client.get(url)
        assert response.status_code == 200
        assert b"Organisation Admin" in response.content

    def test_non_member_cannot_access_org_dashboard(
        self, client, regular_user, organization, disable_rate_limiting
    ):
        """Non-members cannot access an org's recovery dashboard."""
        client.force_login(regular_user)
        url = reverse("surveys:admin_recovery_dashboard") + f"?org={organization.id}"
        response = client.get(url)
        assert response.status_code == 302  # Redirected


class TestTeamOwnerDashboardAccess:
    """Test that team owners can access their scoped dashboard."""

    def test_team_owner_can_access_dashboard(
        self,
        client,
        team_owner,
        standalone_team,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Team owner can access their team's recovery dashboard."""
        client.force_login(team_owner)
        url = (
            reverse("surveys:admin_recovery_dashboard") + f"?team={standalone_team.id}"
        )
        response = client.get(url)
        assert response.status_code == 200
        assert b"Standalone Team Recovery Dashboard" in response.content
        assert b"Team Owner" in response.content

    def test_non_member_cannot_access_team_dashboard(
        self, client, regular_user, standalone_team, disable_rate_limiting
    ):
        """Non-members cannot access a team's recovery dashboard."""
        client.force_login(regular_user)
        url = (
            reverse("surveys:admin_recovery_dashboard") + f"?team={standalone_team.id}"
        )
        response = client.get(url)
        assert response.status_code == 302  # Redirected


class TestScopedRequests:
    """Test that requests are properly scoped to org/team."""

    def test_org_dashboard_only_shows_org_requests(
        self,
        client,
        org_owner,
        organization,
        org_recovery_request,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Org dashboard only shows requests for org surveys."""
        client.force_login(org_owner)
        url = reverse("surveys:admin_recovery_dashboard") + f"?org={organization.id}"
        response = client.get(url)
        assert response.status_code == 200
        # Should see org request
        assert org_recovery_request.request_code.encode() in response.content
        # Should NOT see team request
        assert team_recovery_request.request_code.encode() not in response.content

    def test_team_dashboard_only_shows_team_requests(
        self,
        client,
        team_owner,
        standalone_team,
        org_recovery_request,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Team dashboard only shows requests for team surveys."""
        client.force_login(team_owner)
        url = (
            reverse("surveys:admin_recovery_dashboard") + f"?team={standalone_team.id}"
        )
        response = client.get(url)
        assert response.status_code == 200
        # Should see team request
        assert team_recovery_request.request_code.encode() in response.content
        # Should NOT see org request
        assert org_recovery_request.request_code.encode() not in response.content


class TestOrgAdminApproval:
    """Test org admin approval actions."""

    def test_org_owner_can_approve_primary(
        self,
        client,
        org_owner,
        organization,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Org owner can approve as primary."""
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        response = client.post(url)
        assert response.status_code == 302

        org_recovery_request.refresh_from_db()
        assert org_recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY
        assert org_recovery_request.primary_approver == org_owner

    def test_dual_approval_requires_different_admins(
        self,
        client,
        org_owner,
        org_admin,
        organization,
        org_admin_membership,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Secondary approval must be from different admin."""
        # First: org_owner approves as primary
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        client.post(url)

        org_recovery_request.refresh_from_db()
        assert org_recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY

        # Second: org_owner tries to approve secondary (should fail)
        url = (
            reverse(
                "surveys:admin_recovery_approve_secondary",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        client.post(url)
        org_recovery_request.refresh_from_db()
        # Should still be awaiting secondary (same admin can't approve twice)
        assert org_recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY

        # Third: org_admin approves as secondary (should succeed)
        client.force_login(org_admin)
        client.post(url)
        org_recovery_request.refresh_from_db()
        assert org_recovery_request.status == RecoveryRequest.Status.IN_TIME_DELAY
        assert org_recovery_request.secondary_approver == org_admin


class TestTeamOwnerApproval:
    """Test team owner approval actions."""

    def test_team_owner_can_approve_primary(
        self,
        client,
        team_owner,
        standalone_team,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Team owner can approve as primary."""
        client.force_login(team_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": team_recovery_request.id},
            )
            + f"?team={standalone_team.id}"
        )
        response = client.post(url)
        assert response.status_code == 302

        team_recovery_request.refresh_from_db()
        assert team_recovery_request.status == RecoveryRequest.Status.AWAITING_SECONDARY
        assert team_recovery_request.primary_approver == team_owner


class TestRejectAction:
    """Test rejection actions."""

    def test_org_admin_can_reject(
        self,
        client,
        org_owner,
        organization,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Org admin can reject requests."""
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_reject",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        response = client.post(url, {"reason": "Suspicious request"})
        assert response.status_code == 302

        org_recovery_request.refresh_from_db()
        assert org_recovery_request.status == RecoveryRequest.Status.REJECTED
        assert org_recovery_request.rejected_by == org_owner


class TestCrossOrgAccess:
    """Test that admins cannot access requests outside their scope."""

    def test_org_admin_cannot_approve_team_request(
        self,
        client,
        org_owner,
        organization,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Org admin cannot approve a team's recovery request."""
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": team_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        response = client.post(url)
        assert response.status_code == 403

    def test_team_owner_cannot_approve_org_request(
        self,
        client,
        team_owner,
        standalone_team,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Team owner cannot approve an org's recovery request."""
        client.force_login(team_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?team={standalone_team.id}"
        )
        response = client.post(url)
        assert response.status_code == 403


class TestDetailView:
    """Test detail view access."""

    def test_org_admin_can_view_org_request_detail(
        self,
        client,
        org_owner,
        organization,
        org_recovery_request,
        disable_rate_limiting,
    ):
        """Org admin can view detail of org request."""
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_detail",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        response = client.get(url)
        assert response.status_code == 200
        assert org_recovery_request.request_code.encode() in response.content

    def test_org_admin_cannot_view_team_request_detail(
        self,
        client,
        org_owner,
        organization,
        team_recovery_request,
        disable_rate_limiting,
    ):
        """Org admin cannot view detail of team request."""
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_detail",
                kwargs={"request_id": team_recovery_request.id},
            )
            + f"?org={organization.id}"
        )
        response = client.get(url)
        assert response.status_code == 302  # Redirected with error


@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting on admin recovery dashboard endpoints."""

    def test_dashboard_rate_limited(self, client, org_owner, organization, settings):
        """Dashboard endpoint is rate limited to 20/hour."""
        settings.RATELIMIT_ENABLE = True
        client.force_login(org_owner)
        url = reverse("surveys:admin_recovery_dashboard") + f"?org={organization.id}"

        # Make 21 requests - the 21st should be blocked
        for i in range(21):
            response = client.get(url)
            if i < 20:
                assert response.status_code in [
                    200,
                    302,
                ], f"Request {i+1} should succeed"
            else:
                assert response.status_code == 403, "Request 21 should be rate limited"

    def test_approval_action_rate_limited(
        self, client, org_owner, organization, org_recovery_request, settings
    ):
        """Approval endpoints are rate limited to 5/hour."""
        settings.RATELIMIT_ENABLE = True
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_approve_primary",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )

        # Make 6 requests - the 6th should be blocked
        for i in range(6):
            response = client.post(url)
            if i < 5:
                # First 5 may succeed or redirect (depending on request state)
                assert response.status_code in [
                    200,
                    302,
                    403,
                ], f"Request {i+1} unexpected status"
            else:
                assert response.status_code == 403, "Request 6 should be rate limited"

    def test_reject_action_rate_limited(
        self, client, org_owner, organization, org_recovery_request, settings
    ):
        """Reject endpoint is rate limited to 5/hour."""
        settings.RATELIMIT_ENABLE = True
        client.force_login(org_owner)
        url = (
            reverse(
                "surveys:admin_recovery_reject",
                kwargs={"request_id": org_recovery_request.id},
            )
            + f"?org={organization.id}"
        )

        # Make 6 requests - the 6th should be blocked
        for i in range(6):
            response = client.post(url, {"reason": "Test rejection"})
            if i < 5:
                # First 5 may succeed or redirect (depending on request state)
                assert response.status_code in [
                    200,
                    302,
                    403,
                ], f"Request {i+1} unexpected status"
            else:
                assert response.status_code == 403, "Request 6 should be rate limited"
