"""Tests for switching billing cycle on an existing subscription."""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile

User = get_user_model()


class TestSwitchBillingCycle:
    """Test switching between monthly and annual on an existing subscription.

    GoCardless doesn't support changing interval_unit on an existing
    subscription, so switching requires cancelling the old subscription
    and creating a new one with the new billing cycle.
    """

    @pytest.fixture
    def pro_user_monthly(self, db):
        user = User.objects.create_user(
            username="switch-monthly@example.com",
            email="switch-monthly@example.com",
            password="TestPass123!",
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.payment_provider = "gocardless"
        user.profile.payment_subscription_id = "SUB_EXISTING_MONTHLY"
        user.profile.payment_customer_id = "CU_SWITCH"
        user.profile.payment_mandate_id = "MD_SWITCH"
        user.profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
        user.profile.last_checkout_billing_cycle = "monthly"
        user.profile.save()
        return user

    @pytest.mark.django_db
    def test_switch_to_annual_cancels_old_and_creates_new(
        self, pro_user_monthly, monkeypatch
    ):
        """Switching to annual cancels the old monthly sub and creates a new annual one."""

        cancelled = {}
        created = {}

        def fake_cancel(subscription_id):
            cancelled["subscription_id"] = subscription_id
            return {"id": subscription_id}

        def fake_create_subscription(**kwargs):
            created.update(kwargs)
            return {"id": "SUB_NEW_ANNUAL"}

        monkeypatch.setattr(
            "checktick_app.core.views_billing.payment_client.cancel_subscription",
            fake_cancel,
        )
        monkeypatch.setattr(
            "checktick_app.core.billing.payment_client.create_subscription",
            fake_create_subscription,
        )

        client = Client()
        client.force_login(pro_user_monthly)
        response = client.post(
            reverse("core:switch_billing_cycle"),
            data={"billing_cycle": "annual"},
        )

        assert response.status_code == 302
        assert cancelled["subscription_id"] == "SUB_EXISTING_MONTHLY"
        assert created["interval_unit"] == "yearly"
        assert created["amount"] == 23040  # £230.40 inc VAT annual Pro

        pro_user_monthly.profile.refresh_from_db()
        assert pro_user_monthly.profile.payment_subscription_id == "SUB_NEW_ANNUAL"
        assert pro_user_monthly.profile.last_checkout_billing_cycle == "annual"

    @pytest.mark.django_db
    def test_switch_to_monthly_from_annual(self, pro_user_monthly, monkeypatch):
        """Switching from annual back to monthly works."""

        # Set up as annual subscriber
        pro_user_monthly.profile.last_checkout_billing_cycle = "annual"
        pro_user_monthly.profile.save()

        created = {}
        monkeypatch.setattr(
            "checktick_app.core.views_billing.payment_client.cancel_subscription",
            lambda sub_id: {"id": sub_id},
        )
        monkeypatch.setattr(
            "checktick_app.core.billing.payment_client.create_subscription",
            lambda **kwargs: created.update(kwargs) or {"id": "SUB_NEW_MONTHLY"},
        )

        client = Client()
        client.force_login(pro_user_monthly)
        response = client.post(
            reverse("core:switch_billing_cycle"),
            data={"billing_cycle": "monthly"},
        )

        assert response.status_code == 302
        assert created["interval_unit"] == "monthly"
        assert created["amount"] == 2400  # £24 inc VAT monthly Pro

        pro_user_monthly.profile.refresh_from_db()
        assert pro_user_monthly.profile.last_checkout_billing_cycle == "monthly"

    @pytest.mark.django_db
    def test_switch_invalid_cycle_rejected(self, pro_user_monthly):
        """Switching to an invalid billing cycle is rejected."""

        client = Client()
        client.force_login(pro_user_monthly)
        response = client.post(
            reverse("core:switch_billing_cycle"),
            data={"billing_cycle": "weekly"},
        )

        assert response.status_code == 302
        pro_user_monthly.profile.refresh_from_db()
        assert (
            pro_user_monthly.profile.payment_subscription_id == "SUB_EXISTING_MONTHLY"
        )

    @pytest.mark.django_db
    def test_switch_same_cycle_noop(self, pro_user_monthly, monkeypatch):
        """Switching to the same cycle is a no-op (no cancel/create)."""
        cancel_called = []

        monkeypatch.setattr(
            "checktick_app.core.views_billing.payment_client.cancel_subscription",
            lambda sub_id: cancel_called.append(sub_id) or {"id": sub_id},
        )

        client = Client()
        client.force_login(pro_user_monthly)
        response = client.post(
            reverse("core:switch_billing_cycle"),
            data={"billing_cycle": "monthly"},
        )

        assert response.status_code == 302
        assert len(cancel_called) == 0  # No cancellation
        pro_user_monthly.profile.refresh_from_db()
        assert (
            pro_user_monthly.profile.payment_subscription_id == "SUB_EXISTING_MONTHLY"
        )
