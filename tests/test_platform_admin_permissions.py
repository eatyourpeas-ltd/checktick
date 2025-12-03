"""
Tests for platform admin permissions - ensuring only superusers can access.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.surveys.models import Organization, OrganizationMembership

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(
        username="superadmin",
        email="superadmin@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user (not superuser)."""
    user = User.objects.create_user(
        username="staffuser",
        email="staff@test.com",
        password=TEST_PASSWORD,
    )
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def regular_user(db):
    """Create a regular user."""
    return User.objects.create_user(
        username="regularuser",
        email="regular@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def org_admin_user(db):
    """Create an organization admin (not platform superuser)."""
    user = User.objects.create_user(
        username="orgadmin",
        email="orgadmin@test.com",
        password=TEST_PASSWORD,
    )
    org = Organization.objects.create(name="Test Org", owner=user)
    OrganizationMembership.objects.create(
        organization=org,
        user=user,
        role=OrganizationMembership.Role.ADMIN,
    )
    return user


@pytest.fixture
def test_organization(db, superuser):
    """Create a test organization."""
    owner = User.objects.create_user(
        username="orgowner", email="orgowner@test.com", password=TEST_PASSWORD
    )
    org = Organization.objects.create(
        name="Test Organization",
        owner=owner,
        billing_type=Organization.BillingType.PER_SEAT,
        is_active=True,
        created_by=superuser,
    )
    return org


# ============================================================================
# Platform Admin Dashboard Access Tests
# ============================================================================


@pytest.mark.django_db
class TestPlatformAdminDashboardAccess:
    """Test access control for platform admin dashboard."""

    def test_anonymous_user_redirected_to_login(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied_access(self, client, regular_user):
        """Regular users cannot access platform admin dashboard."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)
        # Should redirect to login (user_passes_test behavior)
        assert response.status_code == 302

    def test_staff_user_denied_access(self, client, staff_user):
        """Staff users (non-superuser) cannot access platform admin dashboard."""
        client.force_login(staff_user)
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_org_admin_denied_access(self, client, org_admin_user):
        """Organization admins cannot access platform admin dashboard."""
        client.force_login(org_admin_user)
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_dashboard(self, client, superuser):
        """Superusers can access platform admin dashboard."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Platform Admin" in response.content


# ============================================================================
# Organization List Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationListAccess:
    """Test access control for organization list."""

    def test_anonymous_user_redirected(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_org_list")
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user):
        """Regular users cannot access organization list."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_org_list")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access(self, client, superuser):
        """Superusers can access organization list."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_list")
        response = client.get(url)
        assert response.status_code == 200


# ============================================================================
# Organization Create Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationCreateAccess:
    """Test access control for organization create."""

    def test_anonymous_user_redirected(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_org_create")
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user):
        """Regular users cannot create organizations via platform admin."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_org_create")
        response = client.get(url)
        assert response.status_code == 302

    def test_org_admin_denied(self, client, org_admin_user):
        """Organization admins cannot create organizations via platform admin."""
        client.force_login(org_admin_user)
        url = reverse("core:platform_admin_org_create")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_create_form(self, client, superuser):
        """Superusers can access organization create form."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_create")
        response = client.get(url)
        assert response.status_code == 200

    def test_superuser_can_create_organization(self, client, superuser):
        """Superusers can create a new organization."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_create")

        response = client.post(
            url,
            {
                "name": "New Test Organization",
                "owner_email": "newowner@example.com",
                "billing_type": "per_seat",
                "price_per_seat": "10.00",
            },
        )

        # Should redirect to detail page
        assert response.status_code == 302
        assert "platform-admin/organizations" in response.url

        # Verify organization was created
        assert Organization.objects.filter(name="New Test Organization").exists()


# ============================================================================
# Organization Detail Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationDetailAccess:
    """Test access control for organization detail view."""

    def test_anonymous_user_redirected(self, client, test_organization):
        """Anonymous users are redirected to login."""
        url = reverse(
            "core:platform_admin_org_detail", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user, test_organization):
        """Regular users cannot view organization details."""
        client.force_login(regular_user)
        url = reverse(
            "core:platform_admin_org_detail", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_org_owner_denied_platform_admin(self, client, test_organization):
        """Organization owner cannot access via platform admin (must use regular views)."""
        client.force_login(test_organization.owner)
        url = reverse(
            "core:platform_admin_org_detail", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_view_any_organization(
        self, client, superuser, test_organization
    ):
        """Superusers can view any organization's details."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_detail", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 200
        assert test_organization.name.encode() in response.content


# ============================================================================
# Organization Edit Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationEditAccess:
    """Test access control for organization edit view."""

    def test_anonymous_user_redirected(self, client, test_organization):
        """Anonymous users are redirected to login."""
        url = reverse(
            "core:platform_admin_org_edit", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user, test_organization):
        """Regular users cannot edit organizations."""
        client.force_login(regular_user)
        url = reverse(
            "core:platform_admin_org_edit", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_edit_organization(
        self, client, superuser, test_organization
    ):
        """Superusers can edit organization details."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_edit", kwargs={"org_id": test_organization.id}
        )

        response = client.post(
            url,
            {
                "name": "Updated Organization Name",
                "billing_type": "flat_rate",
                "flat_rate_price": "500.00",
                "subscription_status": "active",
                "is_active": "on",
            },
        )

        # Should redirect to detail page
        assert response.status_code == 302

        # Verify changes
        test_organization.refresh_from_db()
        assert test_organization.name == "Updated Organization Name"
        assert test_organization.billing_type == Organization.BillingType.FLAT_RATE


# ============================================================================
# Organization Toggle Active Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationToggleActiveAccess:
    """Test access control for organization toggle active."""

    def test_anonymous_user_redirected(self, client, test_organization):
        """Anonymous users are redirected to login."""
        url = reverse(
            "core:platform_admin_org_toggle_active",
            kwargs={"org_id": test_organization.id},
        )
        response = client.post(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied(self, client, regular_user, test_organization):
        """Regular users cannot toggle organization status."""
        client.force_login(regular_user)
        url = reverse(
            "core:platform_admin_org_toggle_active",
            kwargs={"org_id": test_organization.id},
        )
        response = client.post(url)
        assert response.status_code == 302

    def test_superuser_can_toggle_active(self, client, superuser, test_organization):
        """Superusers can toggle organization active status."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_toggle_active",
            kwargs={"org_id": test_organization.id},
        )

        # Organization starts as active
        assert test_organization.is_active is True

        response = client.post(url)
        assert response.status_code == 302

        # Verify it was deactivated
        test_organization.refresh_from_db()
        assert test_organization.is_active is False


# ============================================================================
# Organization Invite Generation Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationInviteAccess:
    """Test access control for organization invite generation."""

    def test_anonymous_user_redirected(self, client, test_organization):
        """Anonymous users are redirected to login."""
        url = reverse(
            "core:platform_admin_org_invite", kwargs={"org_id": test_organization.id}
        )
        response = client.post(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user, test_organization):
        """Regular users cannot generate invite links."""
        client.force_login(regular_user)
        url = reverse(
            "core:platform_admin_org_invite", kwargs={"org_id": test_organization.id}
        )
        response = client.post(url)
        assert response.status_code == 302

    def test_superuser_can_generate_invite(self, client, superuser, test_organization):
        """Superusers can generate organization invite links."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_invite", kwargs={"org_id": test_organization.id}
        )

        # Initially no token
        assert test_organization.setup_token == ""

        response = client.post(url)
        assert response.status_code == 302

        # Verify token was generated
        test_organization.refresh_from_db()
        assert test_organization.setup_token != ""


# ============================================================================
# Organization Stats Access Tests
# ============================================================================


@pytest.mark.django_db
class TestOrganizationStatsAccess:
    """Test access control for organization statistics."""

    def test_anonymous_user_redirected(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_stats")
        response = client.get(url)
        assert response.status_code == 302

    def test_regular_user_denied(self, client, regular_user):
        """Regular users cannot view platform statistics."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_stats")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_view_stats(self, client, superuser):
        """Superusers can view platform statistics."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_stats")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Statistics" in response.content


# ============================================================================
# GET vs POST Method Tests
# ============================================================================


@pytest.mark.django_db
class TestHttpMethodRestrictions:
    """Test that views only accept appropriate HTTP methods."""

    def test_dashboard_rejects_post(self, client, superuser):
        """Dashboard should reject POST requests."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_dashboard")
        response = client.post(url)
        assert response.status_code == 405  # Method Not Allowed

    def test_org_list_rejects_post(self, client, superuser):
        """Organization list should reject POST requests."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_list")
        response = client.post(url)
        assert response.status_code == 405

    def test_toggle_active_rejects_get(self, client, superuser, test_organization):
        """Toggle active should reject GET requests."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_toggle_active",
            kwargs={"org_id": test_organization.id},
        )
        response = client.get(url)
        assert response.status_code == 405

    def test_invite_rejects_get(self, client, superuser, test_organization):
        """Invite generation should reject GET requests."""
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_org_invite", kwargs={"org_id": test_organization.id}
        )
        response = client.get(url)
        assert response.status_code == 405


# ============================================================================
# Non-existent Organization Tests
# ============================================================================


@pytest.mark.django_db
class TestNonExistentOrganization:
    """Test handling of non-existent organization IDs."""

    def test_detail_returns_404(self, client, superuser):
        """Detail view returns 404 for non-existent org."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_detail", kwargs={"org_id": 99999})
        response = client.get(url)
        assert response.status_code == 404

    def test_edit_returns_404(self, client, superuser):
        """Edit view returns 404 for non-existent org."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_edit", kwargs={"org_id": 99999})
        response = client.get(url)
        assert response.status_code == 404

    def test_toggle_returns_404(self, client, superuser):
        """Toggle view returns 404 for non-existent org."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_toggle_active", kwargs={"org_id": 99999})
        response = client.post(url)
        assert response.status_code == 404
