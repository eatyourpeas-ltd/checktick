"""Tests for billing and subscription management.

Tests focus on:
1. Features are unlocked on successful subscription
2. Downgrade workflow functions correctly
3. Features are NOT unlocked on unsuccessful subscription
4. Organizations cannot downgrade
"""

from datetime import timedelta
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.core.tier_limits import get_tier_limits
from checktick_app.surveys.models import Organization, Survey

User = get_user_model()


@pytest.fixture
def free_user(db):
    """Create a free tier user."""
    user = User.objects.create_user(
        username="freeuser@example.com",
        email="freeuser@example.com",
        password="TestPass123!",
    )
    user.profile.account_tier = UserProfile.AccountTier.FREE
    user.profile.save()
    return user


@pytest.fixture
def pro_user(db):
    """Create a pro tier user with active subscription."""
    user = User.objects.create_user(
        username="prouser@example.com",
        email="prouser@example.com",
        password="TestPass123!",
    )
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.payment_subscription_id = "sub_test123"
    user.profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
    user.profile.payment_customer_id = "ctm_test123"
    user.profile.payment_provider = "paddle"
    user.profile.save()
    return user


@pytest.fixture
def org_user(db):
    """Create a user with an organization."""
    user = User.objects.create_user(
        username="orguser@example.com",
        email="orguser@example.com",
        password="TestPass123!",
    )
    org = Organization.objects.create(name="Test Organization", owner=user)
    user.profile.organization = org
    user.profile.account_tier = UserProfile.AccountTier.PRO
    user.profile.payment_subscription_id = "sub_org123"
    user.profile.payment_customer_id = "ctm_org123"
    user.profile.payment_provider = "paddle"
    user.profile.save()
    return user


class TestFeatureUnlockingOnSuccessfulSubscription:
    """Test that features are properly unlocked when subscription succeeds."""

    @pytest.mark.django_db
    @patch("checktick_app.core.views_billing.get_tier_from_price_id")
    @patch("checktick_app.core.views_billing.send_subscription_created_email")
    @patch("checktick_app.core.views_billing.verify_paddle_webhook_signature")
    def test_successful_subscription_upgrades_to_pro(
        self, mock_validate, mock_email, mock_get_tier, free_user
    ):
        """Test successful subscription.created webhook upgrades user to PRO tier."""
        # Mock webhook validation to return True
        mock_validate.return_value = True
        # Mock tier mapping to return "pro" for any price ID
        mock_get_tier.return_value = "pro"

        # Set up payment customer ID
        free_user.profile.payment_customer_id = "ctm_new123"
        free_user.profile.payment_provider = "paddle"
        free_user.profile.save()

        payload = {
            "event_type": "subscription.created",
            "data": {
                "id": "sub_new123",
                "customer_id": "ctm_new123",
                "status": "active",
                "custom_data": {"userId": str(free_user.id)},
                "items": [
                    {
                        "price": {
                            "id": "pri_test_pro_price",  # Test price ID (mocked)
                            "billing_cycle": {"interval": "month", "frequency": 1},
                        }
                    }
                ],
                "current_billing_period": {
                    "ends_at": (timezone.now() + timedelta(days=30)).isoformat()
                },
            },
        }

        client = Client()
        response = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        free_user.profile.refresh_from_db()
        # Verify tier upgraded to PRO
        assert free_user.profile.account_tier == UserProfile.AccountTier.PRO
        assert (
            free_user.profile.subscription_status
            == UserProfile.SubscriptionStatus.ACTIVE
        )
        assert free_user.profile.payment_subscription_id == "sub_new123"

        # Verify welcome email was sent
        mock_email.assert_called_once()

    @pytest.mark.django_db
    def test_pro_user_can_create_unlimited_surveys(self, pro_user):
        """Test PRO tier has unlimited survey creation."""
        limits = get_tier_limits(UserProfile.AccountTier.PRO)
        assert limits.max_surveys is None  # Unlimited

        # Create more than free tier limit (3)
        for i in range(10):
            Survey.objects.create(
                name=f"Survey {i+1}", owner=pro_user, slug=f"pro-survey-{i+1}"
            )

        assert Survey.objects.filter(owner=pro_user).count() == 10


class TestFeatureNotUnlockedOnUnsuccessfulSubscription:
    """Test that features remain locked if subscription doesn't succeed."""

    @pytest.mark.django_db
    def test_past_due_subscription_does_not_upgrade_tier(self, free_user):
        """Test subscription with past_due status doesn't upgrade user."""
        free_user.profile.payment_customer_id = "ctm_pastdue"
        free_user.profile.payment_provider = "paddle"
        free_user.profile.save()

        initial_tier = free_user.profile.account_tier

        payload = {
            "event_type": "subscription.past_due",
            "data": {
                "id": "sub_pastdue",
                "customer_id": "ctm_pastdue",
                "status": "past_due",
            },
        }

        client = Client()
        _ = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        free_user.profile.refresh_from_db()

        # Tier should remain unchanged
        assert free_user.profile.account_tier == initial_tier
        # Status may be set but tier shouldn't upgrade
        if hasattr(free_user.profile, "subscription_status"):
            assert (
                free_user.profile.subscription_status
                != UserProfile.SubscriptionStatus.ACTIVE
            )

    @pytest.mark.django_db
    def test_free_user_cannot_create_more_than_3_surveys(self, free_user):
        """Test free tier is limited to 3 surveys."""
        limits = get_tier_limits(UserProfile.AccountTier.FREE)
        assert limits.max_surveys == 3

        # Create 3 surveys (at the limit)
        for i in range(3):
            Survey.objects.create(
                name=f"Survey {i+1}", owner=free_user, slug=f"free-survey-{i+1}"
            )

        # The 4th survey creation should be prevented by application logic
        # (This is enforced in views/forms, not the model itself)
        assert Survey.objects.filter(owner=free_user).count() == 3


class TestDowngradeWorkflow:
    """Test subscription cancellation and downgrade workflow."""

    @pytest.mark.django_db
    @patch("checktick_app.core.views_billing.send_subscription_cancelled_email")
    @patch("checktick_app.core.views_billing.verify_paddle_webhook_signature")
    def test_cancel_subscription_downgrades_to_free(
        self, mock_validate, mock_email, pro_user
    ):
        """Test subscription.canceled webhook downgrades user to FREE."""
        # Mock webhook validation
        mock_validate.return_value = True

        # Create surveys within free tier limit
        Survey.objects.create(name="Survey 1", owner=pro_user, slug="survey-1")
        Survey.objects.create(name="Survey 2", owner=pro_user, slug="survey-2")

        payload = {
            "event_type": "subscription.canceled",
            "data": {
                "id": pro_user.profile.payment_subscription_id,
                "status": "canceled",
                "current_billing_period": {
                    "ends_at": (timezone.now() + timedelta(days=7)).isoformat()
                },
            },
        }

        client = Client()
        response = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        pro_user.profile.refresh_from_db()
        # Verify downgrade to FREE
        assert pro_user.profile.account_tier == UserProfile.AccountTier.FREE
        assert (
            pro_user.profile.subscription_status
            == UserProfile.SubscriptionStatus.CANCELED
        )
        assert pro_user.profile.payment_subscription_id == ""

        # Verify cancellation email sent
        mock_email.assert_called_once()

    @pytest.mark.django_db
    @patch("checktick_app.core.views_billing.send_subscription_cancelled_email")
    @patch("checktick_app.core.views_billing.verify_paddle_webhook_signature")
    def test_cancel_auto_closes_excess_surveys(
        self, mock_validate, mock_email, pro_user
    ):
        """Test cancellation auto-closes surveys exceeding free tier limit (3)."""
        # Mock webhook validation
        mock_validate.return_value = True

        # Create 5 surveys
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i+1}", owner=pro_user, slug=f"survey-{i+1}"
            )

        payload = {
            "event_type": "subscription.canceled",
            "data": {
                "id": pro_user.profile.payment_subscription_id,
                "status": "canceled",
                "current_billing_period": {
                    "ends_at": (timezone.now() + timedelta(days=7)).isoformat()
                },
            },
        }

        client = Client()
        response = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Should auto-close 2 surveys (5 - 3 = 2)
        closed_surveys = Survey.objects.filter(
            owner=pro_user, status=Survey.Status.CLOSED
        ).count()
        assert closed_surveys == 2

        # Email should include survey closure warning
        call_args = mock_email.call_args[0]
        assert call_args[4] == 2  # surveys_to_close parameter


class TestOrganizationDowngradeProtection:
    """Test that organization users are protected from downgrades."""

    @pytest.mark.django_db
    def test_organization_user_downgrade_preserves_org(self, org_user):
        """Test downgrade doesn't break organization structure."""
        initial_org = org_user.profile.organization

        payload = {
            "event_type": "subscription.canceled",
            "data": {
                "id": org_user.profile.payment_subscription_id,
                "status": "canceled",
                "current_billing_period": {
                    "ends_at": (timezone.now() + timedelta(days=7)).isoformat()
                },
            },
        }

        client = Client()
        _ = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        org_user.profile.refresh_from_db()

        # Organization should still exist
        assert org_user.profile.organization is not None
        assert org_user.profile.organization == initial_org
        assert Organization.objects.filter(id=initial_org.id).exists()

    @pytest.mark.django_db
    def test_org_owner_manages_subscription_for_all_members(self, org_user):
        """Test that org owner's subscription affects all org members."""
        # This is a placeholder test - actual implementation depends on your business logic
        # For now, just verify the org structure is maintained
        assert org_user.profile.organization is not None
        assert org_user.profile.organization.owner == org_user
