"""
Tests for platform admin permissions - ensuring only superusers can access.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.billing import PaymentAPIError
from checktick_app.core.models import Payment, PricingOverride, Promotion, UserProfile
from checktick_app.surveys.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    Team,
)

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

    def test_dashboard_quick_actions_use_account_dropdown_and_platform_stats(
        self, client, superuser
    ):
        """Quick actions should provide create-account dropdown and platform stats link."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_dashboard")
        response = client.get(url)

        assert response.status_code == 200
        assert b"Create Account" in response.content
        assert b"Pending Setups by Tier" in response.content
        assert b"mode=platform" in response.content

    def test_dashboard_includes_promotion_summary(self, client, superuser):
        """Dashboard should show active and scheduled promotion counts."""
        Promotion.objects.create(
            name="Active Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=Decimal("10.00"),
            is_active=True,
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=3),
        )
        Promotion.objects.create(
            name="Scheduled Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=Decimal("5.00"),
            is_active=True,
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=10),
        )

        client.force_login(superuser)
        response = client.get(reverse("core:platform_admin_dashboard"))

        assert response.status_code == 200
        assert b"Active Promotions" in response.content
        assert b"Scheduled Promotions" in response.content
        summary = response.context["promotion_summary"]
        assert summary["active"] == 1
        assert summary["scheduled"] == 1
        assert summary["expiring_soon"] == 1


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

    def test_tier_account_list_shows_active_promotion_and_actions(
        self, client, superuser
    ):
        """Tier account view should include promotion state, expiry, and quick actions."""
        account = User.objects.create_user(
            username="promoted-pro-account",
            email="promoted-pro-account@test.com",
            password=TEST_PASSWORD,
        )
        account.profile.account_tier = UserProfile.AccountTier.PRO
        account.profile.save()

        Promotion.objects.create(
            name="Tier Account Promo",
            scope_type=Promotion.ScopeType.ACCOUNT,
            target_user=account,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=Decimal("10.00"),
            is_active=True,
            ends_at=timezone.now() + timedelta(days=7),
        )

        client.force_login(superuser)
        url = reverse("core:platform_admin_org_list")
        response = client.get(url, {"mode": "tier", "scope": "pro"})

        assert response.status_code == 200
        assert b"Tier Account Promo" in response.content
        assert b"Apply Promotion" in response.content
        assert b"Billing History" in response.content

        users = list(response.context["users"].object_list)
        matched = [u for u in users if u.email == account.email]
        assert matched
        assert matched[0].has_active_promotion is True
        assert matched[0].active_promotion_ends_at is not None

    def test_tier_account_list_includes_apply_and_billing_links(
        self, client, superuser
    ):
        """Tier account rows should include apply-promotion and billing-history links."""
        account = User.objects.create_user(
            username="plain-pro-account",
            email="plain-pro-account@test.com",
            password=TEST_PASSWORD,
        )
        account.profile.account_tier = UserProfile.AccountTier.PRO
        account.profile.save()

        client.force_login(superuser)
        url = reverse("core:platform_admin_org_list")
        response = client.get(url, {"mode": "tier", "scope": "pro"})

        assert response.status_code == 200
        assert f"target_user_email={account.email}".encode() in response.content
        assert b"platform-admin/billing" in response.content
        assert b"q=plain-pro-account" in response.content

    def test_tier_account_list_includes_refund_picker_for_account_payments(
        self, client, superuser
    ):
        """Tier account rows should expose a refund picker for all refundable payments."""
        account = User.objects.create_user(
            username="refund-pro-account",
            email="refund-pro-account@test.com",
            password=TEST_PASSWORD,
        )
        account.profile.account_tier = UserProfile.AccountTier.PRO
        account.profile.save()

        older_payment = Payment.objects.create(
            user=account,
            invoice_number="INV-REFUND-OLDER",
            invoice_date=date(2026, 1, 10),
            payment_provider="gocardless",
            payment_id="PMT-OLDER",
            subscription_id="SUB-OLDER",
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            currency="GBP",
            customer_email=account.email,
            customer_name=account.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )
        latest_payment = Payment.objects.create(
            user=account,
            invoice_number="INV-REFUND-LATEST",
            invoice_date=date(2026, 1, 11),
            payment_provider="gocardless",
            payment_id="PMT-LATEST",
            subscription_id="SUB-LATEST",
            tier="pro",
            amount_ex_vat=700,
            vat_amount=140,
            amount_inc_vat=840,
            vat_rate=0.20,
            currency="GBP",
            customer_email=account.email,
            customer_name=account.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )

        client.force_login(superuser)
        url = reverse("core:platform_admin_org_list")
        response = client.get(url, {"mode": "tier", "scope": "pro"})

        assert response.status_code == 200
        assert b"Refund Payment" in response.content
        assert b"INV-REFUND-OLDER" in response.content
        assert b"INV-REFUND-LATEST" in response.content
        assert (
            reverse(
                "core:platform_admin_billing_refund",
                kwargs={"payment_id": latest_payment.id},
            ).encode()
            in response.content
        )
        assert (
            reverse(
                "core:platform_admin_billing_refund",
                kwargs={"payment_id": older_payment.id},
            ).encode()
            in response.content
        )

        users = list(response.context["users"].object_list)
        matched = [u for u in users if u.email == account.email]
        assert matched
        assert [payment.id for payment in matched[0].refundable_payments] == [
            latest_payment.id,
            older_payment.id,
        ]


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

    def test_superuser_can_add_tier_account_from_create_view(self, client, superuser):
        """Create view should support tier account creation in tier mode."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_create")

        response = client.post(
            f"{url}?mode=tier&scope=team_medium",
            {
                "name": "Tier User",
                "owner_email": "tieruser@example.com",
            },
        )

        assert response.status_code == 302
        assert "mode=tier&scope=team_medium" in response.url

        account = User.objects.get(email="tieruser@example.com")
        assert account.profile.account_tier == UserProfile.AccountTier.TEAM_MEDIUM
        assert (
            account.profile.subscription_status == UserProfile.SubscriptionStatus.ACTIVE
        )
        assert not Organization.objects.filter(name="Tier User").exists()

    def test_superuser_can_add_tier_account_with_promotion(self, client, superuser):
        """Tier account create should optionally apply a promotion in one submit."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_create")

        response = client.post(
            f"{url}?mode=tier&scope=pro",
            {
                "name": "Promo Account",
                "owner_email": "promo-account@example.com",
                "apply_promotion": "on",
                "promotion_name": "Welcome 15%",
                "promotion_effect_type": Promotion.EffectType.PERCENT_DISCOUNT,
                "promotion_effect_value": "15.00",
                "promotion_ends_at": "2030-01-01T12:00",
                "promotion_reason": "Onboarding incentive",
            },
        )

        assert response.status_code == 302
        account = User.objects.get(email="promo-account@example.com")
        promotion = Promotion.objects.get(target_user=account, name="Welcome 15%")
        assert promotion.scope_type == Promotion.ScopeType.ACCOUNT
        assert promotion.effect_type == Promotion.EffectType.PERCENT_DISCOUNT
        assert str(promotion.effect_value) == "15.00"

    def test_invalid_promotion_input_blocks_tier_account_create(
        self, client, superuser
    ):
        """Invalid one-step promotion fields should keep user on form and avoid account create."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_org_create")

        response = client.post(
            f"{url}?mode=tier&scope=pro",
            {
                "name": "Broken Promo Account",
                "owner_email": "broken-promo-account@example.com",
                "apply_promotion": "on",
                "promotion_name": "Broken Promo",
                "promotion_effect_type": Promotion.EffectType.PERCENT_DISCOUNT,
                "promotion_effect_value": "not-a-number",
            },
        )

        assert response.status_code == 200
        assert not User.objects.filter(
            email="broken-promo-account@example.com"
        ).exists()
        assert not Promotion.objects.filter(name="Broken Promo").exists()

    def test_tier_scope_persists_when_scope_missing_in_query(self, client, superuser):
        """Selected tier scope should be retained when moving between pages."""
        client.force_login(superuser)

        dashboard_url = reverse("core:platform_admin_dashboard")
        response = client.get(f"{dashboard_url}?mode=tier&scope=enterprise")
        assert response.status_code == 200
        assert response.context["scope"] == "enterprise"

        list_url = reverse("core:platform_admin_org_list")
        response = client.get(f"{list_url}?mode=tier")
        assert response.status_code == 200
        assert response.context["scope"] == "enterprise"

        stats_url = reverse("core:platform_admin_stats")
        response = client.get(f"{stats_url}?mode=tier")
        assert response.status_code == 200
        assert response.context["scope"] == "enterprise"


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


# ============================================================================
# Platform Logs Access Tests
# ============================================================================


@pytest.mark.django_db
class TestPlatformLogsAccess:
    """Test access control for platform logs view."""

    def test_anonymous_user_redirected_to_login(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_logs")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied_access(self, client, regular_user):
        """Regular users cannot access platform logs."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_logs")
        response = client.get(url)
        assert response.status_code == 302

    def test_staff_user_denied_access(self, client, staff_user):
        """Staff users (non-superuser) cannot access platform logs."""
        client.force_login(staff_user)
        url = reverse("core:platform_admin_logs")
        response = client.get(url)
        assert response.status_code == 302

    def test_org_admin_denied_access(self, client, org_admin_user):
        """Organization admins cannot access platform logs."""
        client.force_login(org_admin_user)
        url = reverse("core:platform_admin_logs")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_logs(self, client, superuser):
        """Superusers can access platform logs."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Platform Logs" in response.content

    def test_superuser_can_filter_by_severity(self, client, superuser):
        """Superusers can filter logs by severity."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.get(url, {"severity": "critical"})
        assert response.status_code == 200

    def test_superuser_can_filter_by_date(self, client, superuser):
        """Superusers can filter logs by date range."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.get(url, {"from": "2025-01-01", "to": "2025-12-31"})
        assert response.status_code == 200

    def test_superuser_can_search_logs(self, client, superuser):
        """Superusers can search logs."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.get(url, {"q": "login"})
        assert response.status_code == 200

    def test_superuser_can_view_infrastructure_logs_tab(self, client, superuser):
        """Superusers can access infrastructure logs tab (even if not configured)."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.get(url, {"source": "infrastructure"})
        assert response.status_code == 200

    def test_logs_rejects_post(self, client, superuser):
        """Logs view should reject POST requests."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_logs")
        response = client.post(url)
        assert response.status_code == 405


# ============================================================================
# Platform Pricing Access Tests
# ============================================================================


@pytest.mark.django_db
class TestPlatformPricingAccess:
    """Test access control and behavior for platform pricing overrides."""

    def test_anonymous_user_redirected_to_login(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_pricing")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied_access(self, client, regular_user):
        """Regular users cannot access platform pricing page."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_pricing")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_pricing(self, client, superuser):
        """Superusers can access pricing override page."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_pricing")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Pricing Overrides" in response.content

    def test_superuser_can_save_override(self, client, superuser):
        """Superusers can create/update a pricing override."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_pricing")

        response = client.post(
            url,
            {
                "pro_amount": "7.00",
                "pro_amount_ex_vat": "5.83",
                "pro_active": "on",
            },
        )
        assert response.status_code == 302

        override = PricingOverride.objects.get(tier="pro")
        assert override.amount == 700
        assert override.amount_ex_vat == 583
        assert override.is_active is True

    def test_pricing_page_rejects_put(self, client, superuser):
        """Pricing page should reject unsupported methods."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_pricing")
        response = client.put(url)
        assert response.status_code == 405

    def test_pricing_page_redirects_from_tier_mode(self, client, superuser):
        """Pricing is platform-level and should redirect away from tier mode query."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_pricing")
        response = client.get(url, {"mode": "tier", "scope": "pro"})
        assert response.status_code == 302
        assert response.url == url


# ============================================================================
# Platform Billing Access Tests
# ============================================================================


@pytest.mark.django_db
class TestPlatformBillingAccess:
    """Test access control and behavior for platform billing view."""

    def test_anonymous_user_redirected_to_login(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_billing")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied_access(self, client, regular_user):
        """Regular users cannot access platform billing page."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_billing")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_billing(self, client, superuser):
        """Superusers can access platform billing page."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_billing")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Billing" in response.content

    def test_billing_rejects_post(self, client, superuser):
        """Billing view should reject POST requests."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_billing")
        response = client.post(url)
        assert response.status_code == 405

    def test_tier_mode_filters_transactions(self, client, superuser, regular_user):
        """Tier mode should filter billing timeline by selected tier."""
        Payment.objects.create(
            user=regular_user,
            invoice_number="INV-TEST-PRO",
            invoice_date=date(2026, 1, 10),
            payment_provider="gocardless",
            payment_id="PMT-PRO-1",
            subscription_id="SUB-PRO-1",
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            currency="GBP",
            customer_email=regular_user.email,
            customer_name=regular_user.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )
        Payment.objects.create(
            user=regular_user,
            invoice_number="INV-TEST-FREE",
            invoice_date=date(2026, 1, 11),
            payment_provider="gocardless",
            payment_id="PMT-FREE-1",
            subscription_id="SUB-FREE-1",
            tier="free",
            amount_ex_vat=0,
            vat_amount=0,
            amount_inc_vat=0,
            vat_rate=0.20,
            currency="GBP",
            customer_email=regular_user.email,
            customer_name=regular_user.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )

        client.force_login(superuser)
        url = reverse("core:platform_admin_billing")
        response = client.get(url, {"mode": "tier", "scope": "pro"})

        assert response.status_code == 200
        assert b"INV-TEST-PRO" in response.content
        assert b"INV-TEST-FREE" not in response.content

    @patch("checktick_app.core.views_platform_admin.PaymentClient")
    def test_superuser_can_refund_confirmed_payment(
        self, mock_payment_client_cls, client, superuser, regular_user
    ):
        """Platform admin should be able to refund confirmed GoCardless payments."""
        payment = Payment.objects.create(
            user=regular_user,
            invoice_number="INV-REFUND-1",
            invoice_date=date(2026, 1, 12),
            payment_provider="gocardless",
            payment_id="PMT-REF-1",
            subscription_id="SUB-REF-1",
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            currency="GBP",
            customer_email=regular_user.email,
            customer_name=regular_user.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )
        mock_payment_client = mock_payment_client_cls.return_value
        mock_payment_client.refund_payment.return_value = {"id": "RF-123"}

        client.force_login(superuser)
        response = client.post(
            reverse(
                "core:platform_admin_billing_refund",
                kwargs={"payment_id": payment.id},
            ),
            {"refund_reason": "Promotion correction", "mode": "platform"},
        )

        assert response.status_code == 302
        payment.refresh_from_db()
        assert payment.status == Payment.PaymentStatus.REFUNDED
        mock_payment_client.refund_payment.assert_called_once_with(
            "PMT-REF-1",
            amount=600,
            total_amount_confirmation=600,
            metadata={
                "invoice_number": "INV-REFUND-1",
                "payment_record_id": str(payment.id),
                "reason": "Promotion correction",
            },
        )

    @patch("checktick_app.core.views_platform_admin.PaymentClient")
    def test_refund_failure_does_not_mark_payment_refunded(
        self, mock_payment_client_cls, client, superuser, regular_user
    ):
        """If provider refund fails, local payment state must remain confirmed."""
        payment = Payment.objects.create(
            user=regular_user,
            invoice_number="INV-REFUND-FAIL",
            invoice_date=date(2026, 1, 13),
            payment_provider="gocardless",
            payment_id="PMT-REF-FAIL",
            subscription_id="SUB-REF-FAIL",
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            currency="GBP",
            customer_email=regular_user.email,
            customer_name=regular_user.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )
        mock_payment_client = mock_payment_client_cls.return_value
        mock_payment_client.refund_payment.side_effect = PaymentAPIError(
            "provider refused"
        )

        client.force_login(superuser)
        response = client.post(
            reverse(
                "core:platform_admin_billing_refund",
                kwargs={"payment_id": payment.id},
            ),
            {"refund_reason": "Promotion correction", "mode": "platform"},
        )

        assert response.status_code == 302
        payment.refresh_from_db()
        assert payment.status == Payment.PaymentStatus.CONFIRMED

    @patch("checktick_app.core.views_platform_admin.PaymentClient")
    def test_refund_from_tier_account_list_returns_to_account_list(
        self, mock_payment_client_cls, client, superuser, regular_user
    ):
        """Refund posts from the tier account list should return to the same tier list URL."""
        regular_user.profile.account_tier = UserProfile.AccountTier.PRO
        regular_user.profile.save(update_fields=["account_tier", "updated_at"])

        payment = Payment.objects.create(
            user=regular_user,
            invoice_number="INV-REFUND-RETURN",
            invoice_date=date(2026, 1, 14),
            payment_provider="gocardless",
            payment_id="PMT-REF-RETURN",
            subscription_id="SUB-REF-RETURN",
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            currency="GBP",
            customer_email=regular_user.email,
            customer_name=regular_user.username,
            status=Payment.PaymentStatus.CONFIRMED,
        )
        mock_payment_client = mock_payment_client_cls.return_value
        mock_payment_client.refund_payment.return_value = {"id": "RF-RETURN"}

        client.force_login(superuser)
        return_to = f"{reverse('core:platform_admin_org_list')}?mode=tier&scope=pro"
        response = client.post(
            reverse(
                "core:platform_admin_billing_refund",
                kwargs={"payment_id": payment.id},
            ),
            {"return_to": return_to},
        )

        assert response.status_code == 302
        assert response.url == return_to


# ============================================================================
# Platform Promotions Access Tests
# ============================================================================


@pytest.mark.django_db
class TestPlatformPromotionsAccess:
    """Test access control and basic behavior for platform promotions views."""

    def test_anonymous_user_redirected_to_login(self, client):
        """Anonymous users are redirected to login."""
        url = reverse("core:platform_admin_promotions")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response.url.lower()

    def test_regular_user_denied_access(self, client, regular_user):
        """Regular users cannot access promotions page."""
        client.force_login(regular_user)
        url = reverse("core:platform_admin_promotions")
        response = client.get(url)
        assert response.status_code == 302

    def test_superuser_can_access_promotions(self, client, superuser):
        """Superusers can access promotions listing."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_promotions")
        response = client.get(url)
        assert response.status_code == 200
        assert b"Promotions" in response.content

    def test_superuser_can_create_platform_promotion(self, client, superuser):
        """Superusers can create a platform-scope promotion."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_promotion_create")
        response = client.post(
            url,
            {
                "name": "Summer Promo",
                "code": "SUMMER2026",
                "scope_type": "platform",
                "effect_type": "percent_discount",
                "effect_value": "10.00",
                "priority": "50",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        assert Promotion.objects.filter(name="Summer Promo").exists()

    def test_superuser_can_toggle_promotion(self, client, superuser):
        """Superusers can activate/deactivate a promotion."""
        promotion = Promotion.objects.create(
            name="Toggle Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=5,
            is_active=True,
        )
        client.force_login(superuser)
        url = reverse(
            "core:platform_admin_promotion_toggle",
            kwargs={"promotion_id": promotion.id},
        )
        response = client.post(url)
        assert response.status_code == 302

        promotion.refresh_from_db()
        assert promotion.is_active is False
        assert AuditLog.objects.filter(
            action=AuditLog.Action.UPDATE,
            metadata__promotion_id=str(promotion.id),
        ).exists()

    def test_superuser_can_edit_scheduled_promotion(self, client, superuser):
        """Scheduled promotions can be edited before they start."""
        promotion = Promotion.objects.create(
            name="Editable Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )
        client.force_login(superuser)

        response = client.post(
            reverse(
                "core:platform_admin_promotion_edit",
                kwargs={"promotion_id": promotion.id},
            ),
            {
                "name": "Editable Promo Updated",
                "code": "",
                "description": "Updated",
                "scope_type": Promotion.ScopeType.PLATFORM,
                "target_tier": "",
                "effect_type": Promotion.EffectType.PERCENT_DISCOUNT,
                "effect_value": "15.00",
                "effect_tier": "",
                "priority": "100",
                "starts_at": (timezone.now() + timedelta(days=3)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "ends_at": "",
                "reason": "Refined offer",
                "internal_notes": "Ops note",
                "is_active": "on",
            },
        )

        assert response.status_code == 302
        promotion.refresh_from_db()
        assert promotion.name == "Editable Promo Updated"
        assert str(promotion.effect_value) == "15.00"
        assert AuditLog.objects.filter(
            action=AuditLog.Action.UPDATE,
            metadata__promotion_id=str(promotion.id),
        ).exists()

    def test_started_promotion_edit_rejects_billing_term_change(
        self, client, superuser
    ):
        """Started promotions should reject billing-impacting edits in admin UI."""
        promotion = Promotion.objects.create(
            name="Started Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )
        client.force_login(superuser)

        response = client.post(
            reverse(
                "core:platform_admin_promotion_edit",
                kwargs={"promotion_id": promotion.id},
            ),
            {
                "name": "Started Promo",
                "code": "",
                "description": "",
                "scope_type": Promotion.ScopeType.PLATFORM,
                "target_tier": "",
                "effect_type": Promotion.EffectType.PERCENT_DISCOUNT,
                "effect_value": "25.00",
                "effect_tier": "",
                "priority": "100",
                "starts_at": (timezone.now() - timedelta(days=1)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "ends_at": "",
                "reason": "",
                "internal_notes": "",
                "is_active": "on",
            },
        )

        assert response.status_code == 200
        assert b"cannot be edited in place" in response.content
        promotion.refresh_from_db()
        assert str(promotion.effect_value) == "10.00"

    def test_duplicate_promotion_prefills_create_form(self, client, superuser):
        """Duplicate action should open create form prefilled from the source promotion."""
        promotion = Promotion.objects.create(
            name="Source Promo",
            code="SRC",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            is_active=True,
        )
        client.force_login(superuser)
        response = client.get(
            reverse(
                "core:platform_admin_promotion_duplicate",
                kwargs={"promotion_id": promotion.id},
            )
        )

        assert response.status_code == 200
        assert b"Source Promo Copy" in response.content
        assert b"Creating a new promotion based on" in response.content

    def test_revoke_promotion_ends_it_immediately(self, client, superuser):
        """Revoking a promotion should deactivate it and end its window now."""
        promotion = Promotion.objects.create(
            name="Revokable Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() - timedelta(days=2),
            is_active=True,
        )
        client.force_login(superuser)
        response = client.post(
            reverse(
                "core:platform_admin_promotion_revoke",
                kwargs={"promotion_id": promotion.id},
            )
        )

        assert response.status_code == 302
        promotion.refresh_from_db()
        assert promotion.is_active is False
        assert promotion.ends_at is not None
        assert AuditLog.objects.filter(
            action=AuditLog.Action.REMOVE,
            metadata__promotion_id=str(promotion.id),
        ).exists()

    def test_tier_mode_filters_promotions_by_selected_scope(self, client, superuser):
        """Tier mode should only surface promotions relevant to selected tier scope."""
        pro_user = User.objects.create_user(
            username="promo-pro-user",
            email="promo-pro-user@test.com",
            password=TEST_PASSWORD,
        )
        pro_user.profile.account_tier = UserProfile.AccountTier.PRO
        pro_user.profile.save()
        team_owner = User.objects.create_user(
            username="promo-team-owner",
            email="promo-team-owner@test.com",
            password=TEST_PASSWORD,
        )
        team_owner.profile.account_tier = UserProfile.AccountTier.TEAM_SMALL
        team_owner.profile.save()
        team = Team.objects.create(
            name="Promo Team", owner=team_owner, size=Team.Size.SMALL
        )

        Promotion.objects.create(
            name="Global Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=5,
            is_active=True,
        )
        Promotion.objects.create(
            name="Team Small Tier Promo",
            scope_type=Promotion.ScopeType.TIER,
            target_tier=UserProfile.AccountTier.TEAM_SMALL,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            is_active=True,
        )
        Promotion.objects.create(
            name="Pro User Promo",
            scope_type=Promotion.ScopeType.ACCOUNT,
            target_user=pro_user,
            effect_type=Promotion.EffectType.FIXED_DISCOUNT,
            effect_value=2,
            is_active=True,
        )
        Promotion.objects.create(
            name="Team Account Promo",
            scope_type=Promotion.ScopeType.ACCOUNT,
            target_team=team,
            effect_type=Promotion.EffectType.FIXED_DISCOUNT,
            effect_value=3,
            is_active=True,
        )

        client.force_login(superuser)
        url = reverse("core:platform_admin_promotions")
        response = client.get(url, {"mode": "tier", "scope": "team_small"})

        assert response.status_code == 200
        assert b"Global Promo" in response.content
        assert b"Team Small Tier Promo" in response.content
        assert b"Team Account Promo" in response.content
        assert b"Pro User Promo" not in response.content

    def test_tier_mode_create_defaults_target_tier(self, client, superuser):
        """Tier mode creation should default tier-scope promotion target tier to selected scope."""
        client.force_login(superuser)
        url = reverse("core:platform_admin_promotion_create")
        response = client.post(
            f"{url}?mode=tier&scope=team_medium",
            {
                "name": "Tier Mode Promo",
                "scope_type": "tier",
                "target_tier": "",
                "effect_type": "percent_discount",
                "effect_value": "10.00",
                "priority": "50",
                "is_active": "on",
            },
        )

        assert response.status_code == 302
        promotion = Promotion.objects.get(name="Tier Mode Promo")
        assert promotion.target_tier == UserProfile.AccountTier.TEAM_MEDIUM
