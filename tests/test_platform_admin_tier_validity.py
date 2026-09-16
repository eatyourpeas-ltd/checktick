"""Tests for the platform admin tier-account creation form with validity.

Covers the new tier dropdown and renewal date controls added to
organization_create when create_target == 'account' (mode=tier,
scope != organization).

Verifies:
- Tier dropdown sets account_tier (overriding the scope query param).
- Validity presets (1/2/5 years) set subscription_current_period_end.
- Custom date works and is validated (must be future, max 5 years).
- Free tier ignores validity (no expiry).
- Organization/Enterprise default to no expiry but allow optional renewal.
- Pro/Team require a renewal date.
- Re-subscription re-opens auto-closed surveys.
- Downgrade to free via the form closes excess surveys immediately.
"""

from datetime import timedelta
import secrets

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import Survey

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="superadmin_tier",
        email="superadmin-tier@test.com",
        password=TEST_PASSWORD,
    )


def _unique_email():
    return f"tier-user-{secrets.token_hex(8)}@example.com"


def _post_create(client, superuser, **extra):
    """POST to organization_create with mode=tier and given form fields."""
    client.force_login(superuser)
    base = {
        "name": "Test Account",
        "owner_email": _unique_email(),
        "tier": "pro",
        "validity_preset": "1_year",
    }
    base.update(extra)
    return client.post(
        reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
        base,
    )


@pytest.mark.django_db
class TestTierAccountCreation:
    """Test the tier dropdown and validity controls."""

    def test_pro_with_1_year_preset_sets_period_end(self, client, superuser):
        """Pro tier with 1_year preset sets subscription_current_period_end ~365 days out."""
        email = _unique_email()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "name": "Pro User",
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 302

        user = User.objects.get(email=email)
        assert user.profile.account_tier == UserProfile.AccountTier.PRO
        assert user.profile.subscription_status == UserProfile.SubscriptionStatus.ACTIVE
        assert user.profile.subscription_current_period_end is not None
        # ~365 days from now (allow 2 days slack for test runtime).
        delta = user.profile.subscription_current_period_end - timezone.now()
        assert 360 <= delta.days <= 370

    def test_pro_with_5_year_preset(self, client, superuser):
        """5_years preset sets period_end ~1825 days out."""
        email = _unique_email()
        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "5_years",
            },
        )
        user = User.objects.get(email=email)
        delta = user.profile.subscription_current_period_end - timezone.now()
        assert 1820 <= delta.days <= 1830

    def test_pro_with_custom_date(self, client, superuser):
        """Custom date sets the exact period_end."""
        email = _unique_email()
        target = (timezone.now() + timedelta(days=100)).date().isoformat()
        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "custom",
                "valid_until": target,
            },
        )
        user = User.objects.get(email=email)
        delta = user.profile.subscription_current_period_end - timezone.now()
        assert 99 <= delta.days <= 101

    def test_free_tier_ignores_validity(self, client, superuser):
        """Free tier sets no expiry regardless of validity_preset."""
        email = _unique_email()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "free",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(email=email)
        assert user.profile.account_tier == UserProfile.AccountTier.FREE
        assert user.profile.subscription_current_period_end is None
        assert user.profile.subscription_status == UserProfile.SubscriptionStatus.NONE

    def test_organization_defaults_to_no_expiry(self, client, superuser):
        """Organization tier with 'none' preset has no expiry."""
        email = _unique_email()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "organization",
                "validity_preset": "none",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(email=email)
        assert user.profile.account_tier == UserProfile.AccountTier.ORGANIZATION
        assert user.profile.subscription_current_period_end is None

    def test_organization_with_optional_renewal(self, client, superuser):
        """Organization tier can optionally set a renewal date."""
        email = _unique_email()
        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "organization",
                "validity_preset": "1_year",
            },
        )
        user = User.objects.get(email=email)
        assert user.profile.subscription_current_period_end is not None

    def test_pro_requires_renewal_date(self, client, superuser):
        """Pro tier with 'none' preset is rejected."""
        email = _unique_email()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "none",
            },
        )
        # Form re-renders with error (200, not redirect).
        assert response.status_code == 200
        assert b"renewal date is required" in response.content.lower()
        assert not User.objects.filter(email=email).exists()

    def test_custom_date_in_past_rejected(self, client, superuser):
        """Custom date in the past is rejected."""
        email = _unique_email()
        past = (timezone.now() - timedelta(days=10)).date().isoformat()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "custom",
                "valid_until": past,
            },
        )
        assert response.status_code == 200
        assert b"must be in the future" in response.content.lower()

    def test_custom_date_over_5_years_rejected(self, client, superuser):
        """Custom date more than 5 years out is rejected."""
        email = _unique_email()
        far = (timezone.now() + timedelta(days=365 * 6)).date().isoformat()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "custom",
                "valid_until": far,
            },
        )
        assert response.status_code == 200
        assert b"5 years" in response.content

    def test_invalid_tier_rejected(self, client, superuser):
        """An invalid tier value is rejected."""
        email = _unique_email()
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "not_a_tier",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 200
        assert b"valid tier is required" in response.content.lower()

    def test_warning_flags_reset_on_new_expiry(self, client, superuser):
        """Setting a new expiry clears the warning tracking fields."""
        email = _unique_email()
        # Create a user with stale warning flags.
        user = User.objects.create_user(
            username=email, email=email, password=TEST_PASSWORD
        )
        user.profile.last_expiry_warning_stage = "1week"
        user.profile.last_expiry_warning_sent_at = timezone.now() - timedelta(days=5)
        user.profile.save()
        UserProfile.objects.filter(pk=user.profile.pk).update(
            last_expiry_warning_sent_at=timezone.now() - timedelta(days=5)
        )

        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "2_years",
            },
        )
        user.profile.refresh_from_db()
        assert user.profile.last_expiry_warning_stage == ""
        assert user.profile.last_expiry_warning_sent_at is None


@pytest.mark.django_db
class TestTierAccountReopenOnUpgrade:
    """Test that upgrading via the form re-opens auto-closed surveys."""

    def test_upgrade_reopens_auto_closed_surveys(self, client, superuser):
        """Upgrading a lapsed user via the form re-opens auto-closed surveys."""
        email = _unique_email()
        user = User.objects.create_user(
            username=email, email=email, password=TEST_PASSWORD
        )
        # Simulate a previously-pro user who was downgraded.
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i + 1}",
                owner=user,
                slug=f"reopen-form-{i + 1}",
            )
        user.profile.force_downgrade_tier(UserProfile.AccountTier.FREE)
        assert (
            Survey.objects.filter(
                owner=user, status=Survey.Status.CLOSED, closed_by_downgrade=True
            ).count()
            == 2
        )

        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "pro",
                "validity_preset": "1_year",
            },
        )
        assert (
            Survey.objects.filter(
                owner=user, status=Survey.Status.CLOSED, closed_by_downgrade=True
            ).count()
            == 0
        )

    def test_downgrade_to_free_closes_excess_surveys(self, client, superuser):
        """Downgrading a pro user to free via the form closes excess surveys."""
        email = _unique_email()
        user = User.objects.create_user(
            username=email, email=email, password=TEST_PASSWORD
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.save()
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i + 1}",
                owner=user,
                slug=f"downgrade-form-{i + 1}",
            )

        client.force_login(superuser)
        client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            {
                "owner_email": email,
                "tier": "free",
                "validity_preset": "1_year",
            },
        )
        assert (
            Survey.objects.filter(owner=user, status=Survey.Status.CLOSED).count() == 2
        )
