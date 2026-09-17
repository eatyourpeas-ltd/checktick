"""Tests for manual upgrade lifecycle: grace period, audit log, email.

Covers:
1. Grace period: manually upgraded accounts get a 7-day grace period
   before downgrade when their valid_until date passes.
2. Audit log: manual tier changes create an AuditLog entry.
3. Email: manual upgrade to a paid tier sends a notification email.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import AuditLog

User = get_user_model()
TEST_PASSWORD = "x"


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin_grace@example.com",
        email="admin_grace@example.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def manually_upgraded_user(db):
    """A user whose account was manually upgraded to Pro with a past expiry."""
    user = User.objects.create_user(
        username="manual_grace@example.com",
        password=TEST_PASSWORD,
        email="manual_grace@example.com",
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
    # No payment_subscription_id — this is a manual upgrade.
    user.profile.subscription_current_period_end = timezone.now() - timedelta(days=3)
    user.profile.save()
    return user


@pytest.fixture
def gocardless_user(db):
    """A user with a GoCardless subscription whose period end has passed."""
    user = User.objects.create_user(
        username="gc_grace@example.com",
        password=TEST_PASSWORD,
        email="gc_grace@example.com",
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    user.profile.payment_subscription_id = "sub_test_123"
    user.profile.payment_provider = "gocardless"
    user.profile.subscription_current_period_end = timezone.now() - timedelta(days=3)
    user.profile.save()
    return user


@pytest.mark.django_db
class TestManualUpgradeGracePeriod:
    """Test that manually upgraded accounts get a 7-day grace period."""

    def test_manual_upgrade_within_grace_not_downgraded(self, manually_upgraded_user):
        """A manually upgraded user 3 days past expiry is NOT downgraded
        (within the 7-day grace period)."""
        from django.core.management import call_command

        call_command("process_expired_subscriptions")

        manually_upgraded_user.profile.refresh_from_db()
        assert (
            manually_upgraded_user.profile.account_tier == UserProfile.AccountTier.PRO
        )

    def test_manual_upgrade_past_grace_downgraded(self, manually_upgraded_user):
        """A manually upgraded user 10 days past expiry IS downgraded
        (past the 7-day grace period)."""
        from django.core.management import call_command

        # Move expiry to 10 days ago (past the 7-day grace period).
        UserProfile.objects.filter(pk=manually_upgraded_user.profile.pk).update(
            subscription_current_period_end=timezone.now() - timedelta(days=10)
        )

        call_command("process_expired_subscriptions")

        manually_upgraded_user.profile.refresh_from_db()
        assert (
            manually_upgraded_user.profile.account_tier == UserProfile.AccountTier.FREE
        )

    def test_gocardless_no_grace_period(self, gocardless_user):
        """A GoCardless user 3 days past expiry IS downgraded immediately
        (no grace period for GoCardless — they've already had notice from
        the provider)."""
        from django.core.management import call_command

        call_command("process_expired_subscriptions")

        gocardless_user.profile.refresh_from_db()
        assert gocardless_user.profile.account_tier == UserProfile.AccountTier.FREE


@pytest.mark.django_db
class TestManualUpgradeAuditLog:
    """Test that manual tier changes create an AuditLog entry."""

    def test_manual_upgrade_creates_audit_log(self, client, superuser):
        """POSTing a manual upgrade via organization_create creates an
        AuditLog entry."""
        from django.urls import reverse

        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            data={
                "owner_email": "audit_test@example.com",
                "tier": "pro",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 302

        # Check an audit log was created.
        target = User.objects.get(email="audit_test@example.com")
        audit_entries = AuditLog.objects.filter(
            target_user=target,
            action=AuditLog.Action.UPDATE,
        )
        assert audit_entries.exists()
        entry = audit_entries.first()
        assert "Manual tier change" in entry.message
        assert "pro" in entry.message
        assert entry.actor == superuser


@pytest.mark.django_db
class TestManualUpgradeEmail:
    """Test that manual upgrade sends a notification email."""

    @patch("checktick_app.core.email_utils.send_manual_upgrade_email")
    def test_manual_upgrade_sends_email(self, mock_email, client, superuser):
        """Upgrading to a paid tier sends an email notification."""
        from django.urls import reverse

        mock_email.return_value = True
        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            data={
                "owner_email": "email_test@example.com",
                "tier": "pro",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 302
        mock_email.assert_called_once()

    @patch("checktick_app.core.email_utils.send_manual_upgrade_email")
    def test_downgrade_to_free_no_email(self, mock_email, client, superuser):
        """Downgrading to free does NOT send an upgrade email."""
        from django.urls import reverse

        # Create a user first.
        User.objects.create_user(
            username="downgrade_test@example.com",
            email="downgrade_test@example.com",
            password=TEST_PASSWORD,
        )

        client.force_login(superuser)
        response = client.post(
            reverse("core:platform_admin_org_create") + "?mode=tier&scope=pro",
            data={
                "owner_email": "downgrade_test@example.com",
                "tier": "free",
                "validity_preset": "1_year",
            },
        )
        assert response.status_code == 302
        mock_email.assert_not_called()
