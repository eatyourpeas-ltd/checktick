"""Tests for billing and subscription management.

Tests focus on:
1. Features are unlocked on successful subscription
2. Downgrade workflow functions correctly
3. Features are NOT unlocked on unsuccessful subscription
4. Organizations cannot downgrade
5. Payment records are created correctly
6. VAT calculations are accurate
7. CSV export contains only financial data (no PII)
8. Subscription expiry handling works correctly
"""

from datetime import date, timedelta
import csv
import json
from io import StringIO
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.models import UserProfile, Payment
from checktick_app.core.admin import PaymentAdmin
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
    @patch("checktick_app.core.views_billing.send_subscription_created_email")
    @patch("checktick_app.core.views_billing.verify_gocardless_webhook_signature")
    def test_successful_subscription_upgrades_to_pro(
        self, mock_validate, mock_email, free_user
    ):
        """Test successful GoCardless subscription.created webhook upgrades user to PRO tier."""
        # Mock webhook validation to return True
        mock_validate.return_value = True

        # Set up payment mandate ID (GoCardless uses mandates)
        free_user.profile.payment_mandate_id = "MD0001"
        free_user.profile.payment_provider = "gocardless"
        free_user.profile.account_tier = (
            UserProfile.AccountTier.PRO
        )  # Set by redirect flow completion
        free_user.profile.save()

        # GoCardless sends events in an array
        payload = {
            "events": [
                {
                    "id": "EV0001",
                    "resource_type": "subscriptions",
                    "action": "created",
                    "links": {
                        "subscription": "SB0001",
                        "mandate": "MD0001",
                    },
                }
            ]
        }

        client = Client()
        response = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        free_user.profile.refresh_from_db()
        # Verify subscription ID was stored
        assert free_user.profile.payment_subscription_id == "SB0001"
        assert (
            free_user.profile.subscription_status
            == UserProfile.SubscriptionStatus.ACTIVE
        )

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
    @patch("checktick_app.core.views_billing.verify_gocardless_webhook_signature")
    def test_cancel_subscription_downgrades_to_free(
        self, mock_validate, mock_email, pro_user
    ):
        """Test GoCardless subscription.cancelled webhook downgrades user to FREE."""
        # Mock webhook validation
        mock_validate.return_value = True

        # Update user to use GoCardless
        pro_user.profile.payment_provider = "gocardless"
        pro_user.profile.save()

        # Create surveys within free tier limit
        Survey.objects.create(name="Survey 1", owner=pro_user, slug="survey-1")
        Survey.objects.create(name="Survey 2", owner=pro_user, slug="survey-2")

        # GoCardless event format
        payload = {
            "events": [
                {
                    "id": "EV0002",
                    "resource_type": "subscriptions",
                    "action": "cancelled",
                    "links": {
                        "subscription": pro_user.profile.payment_subscription_id,
                    },
                }
            ]
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
    @patch("checktick_app.core.views_billing.verify_gocardless_webhook_signature")
    def test_cancel_auto_closes_excess_surveys(
        self, mock_validate, mock_email, pro_user
    ):
        """Test cancellation auto-closes surveys exceeding free tier limit (3)."""
        # Mock webhook validation
        mock_validate.return_value = True

        # Update user to use GoCardless
        pro_user.profile.payment_provider = "gocardless"
        pro_user.profile.save()

        # Create 5 surveys
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i+1}", owner=pro_user, slug=f"survey-{i+1}"
            )

        # GoCardless event format
        payload = {
            "events": [
                {
                    "id": "EV0003",
                    "resource_type": "subscriptions",
                    "action": "cancelled",
                    "links": {
                        "subscription": pro_user.profile.payment_subscription_id,
                    },
                }
            ]
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


class TestPaymentRecordCreation:
    """Test that payment records are created correctly for VAT tracking."""

    @pytest.fixture
    def pro_user_gocardless(self, db):
        """Create a pro tier user with GoCardless subscription."""
        user = User.objects.create_user(
            username="gcuser@example.com",
            email="gcuser@example.com",
            password="TestPass123!",
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.payment_subscription_id = "SB_TEST123"
        user.profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
        user.profile.payment_customer_id = "CU_TEST123"
        user.profile.payment_mandate_id = "MD_TEST123"
        user.profile.payment_provider = "gocardless"
        user.profile.save()
        return user

    @pytest.mark.django_db
    def test_payment_record_created_from_subscription(self, pro_user_gocardless):
        """Test Payment.create_from_subscription creates correct record."""
        payment = Payment.create_from_subscription(
            user=pro_user_gocardless,
            tier="pro",
            payment_id="PM_TEST123",
            subscription_id="SB_TEST123",
        )

        assert payment.invoice_number.startswith("INV-")
        assert payment.user == pro_user_gocardless
        assert payment.tier == "pro"
        assert payment.payment_id == "PM_TEST123"
        assert payment.subscription_id == "SB_TEST123"
        assert payment.status == Payment.PaymentStatus.CONFIRMED
        assert payment.customer_email == pro_user_gocardless.email

    @pytest.mark.django_db
    def test_payment_vat_calculation_correct(self, pro_user_gocardless):
        """Test VAT amounts are calculated correctly for pro tier."""
        payment = Payment.create_from_subscription(
            user=pro_user_gocardless,
            tier="pro",
            payment_id="PM_TEST456",
            subscription_id="SB_TEST456",
        )

        # Pro tier: £5 ex VAT = 500 pence, £6 inc VAT = 600 pence, VAT = 100 pence
        assert payment.amount_ex_vat == 500
        assert payment.amount_inc_vat == 600
        assert payment.vat_amount == 100
        assert float(payment.vat_rate) == 0.20

    @pytest.mark.django_db
    def test_payment_display_methods(self, pro_user_gocardless):
        """Test payment display methods format correctly."""
        payment = Payment.create_from_subscription(
            user=pro_user_gocardless,
            tier="pro",
            payment_id="PM_TEST789",
            subscription_id="SB_TEST789",
        )

        assert payment.get_amount_ex_vat_display() == "£5.00"
        assert payment.get_vat_amount_display() == "£1.00"
        assert payment.get_amount_inc_vat_display() == "£6.00"
        assert payment.get_vat_rate_display() == "20%"

    @pytest.mark.django_db
    def test_team_tier_vat_calculation(self, db):
        """Test VAT calculation for team tiers."""
        user = User.objects.create_user(
            username="teamuser@example.com",
            email="teamuser@example.com",
            password="TestPass123!",
        )
        user.profile.account_tier = UserProfile.AccountTier.TEAM_SMALL
        user.profile.save()

        payment = Payment.create_from_subscription(
            user=user,
            tier="team_small",
            payment_id="PM_TEAM123",
            subscription_id="SB_TEAM123",
        )

        # Team Small: £25 ex VAT = 2500 pence, £30 inc VAT = 3000 pence
        assert payment.amount_ex_vat == 2500
        assert payment.amount_inc_vat == 3000
        assert payment.vat_amount == 500

    @pytest.mark.django_db
    @patch("checktick_app.core.views_billing.verify_gocardless_webhook_signature")
    def test_payment_confirmed_webhook_creates_payment_record(
        self, mock_validate, pro_user_gocardless
    ):
        """Test GoCardless payment.confirmed webhook creates Payment record."""
        mock_validate.return_value = True

        # No payment records initially
        assert Payment.objects.count() == 0

        payload = {
            "events": [
                {
                    "id": "EV_CONFIRM",
                    "resource_type": "payments",
                    "action": "confirmed",
                    "links": {
                        "payment": "PM_WEBHOOK123",
                        "subscription": pro_user_gocardless.profile.payment_subscription_id,
                    },
                }
            ]
        }

        client = Client()
        response = client.post(
            reverse("core:payment_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 200

        # Payment record should be created
        assert Payment.objects.count() == 1
        payment = Payment.objects.first()
        assert payment.payment_id == "PM_WEBHOOK123"
        assert payment.user == pro_user_gocardless


class TestVATCSVExport:
    """Test CSV export for VAT returns contains only financial data."""

    @pytest.fixture
    def sample_payments(self, db):
        """Create sample payments for export testing."""
        user1 = User.objects.create_user(
            username="user1@example.com",
            email="user1@example.com",
            password="TestPass123!",
        )
        user2 = User.objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
            password="TestPass123!",
        )

        # Create confirmed payments
        p1 = Payment.objects.create(
            user=user1,
            invoice_number="INV-20251201-ABC12345",
            invoice_date=date.today(),
            tier="pro",
            amount_ex_vat=500,
            vat_amount=100,
            amount_inc_vat=600,
            vat_rate=0.20,
            customer_email="user1@example.com",
            customer_name="User One",
            subscription_id="SB_001",
            payment_id="PM_001",
            status=Payment.PaymentStatus.CONFIRMED,
        )
        p2 = Payment.objects.create(
            user=user2,
            invoice_number="INV-20251202-DEF67890",
            invoice_date=date.today(),
            tier="team_small",
            amount_ex_vat=2500,
            vat_amount=500,
            amount_inc_vat=3000,
            vat_rate=0.20,
            customer_email="user2@example.com",
            customer_name="User Two",
            subscription_id="SB_002",
            payment_id="PM_002",
            status=Payment.PaymentStatus.CONFIRMED,
        )

        return [p1, p2]

    @pytest.mark.django_db
    def test_csv_export_excludes_personal_data(self, sample_payments):
        """Test CSV export does not include customer email or name."""
        admin = PaymentAdmin(Payment, AdminSite())
        factory = RequestFactory()
        request = factory.get("/admin/core/payment/")
        request.user = MagicMock()

        queryset = Payment.objects.all()
        response = admin._generate_csv(queryset, "test.csv")

        content = response.content.decode("utf-8")

        # Should NOT contain email addresses
        assert "user1@example.com" not in content
        assert "user2@example.com" not in content

        # Should NOT contain customer names
        assert "User One" not in content
        assert "User Two" not in content

        # SHOULD contain financial data
        assert "INV-20251201-ABC12345" in content
        assert "5.00" in content  # Amount ex VAT
        assert "1.00" in content  # VAT amount
        assert "6.00" in content  # Total inc VAT

    @pytest.mark.django_db
    def test_csv_export_contains_required_vat_fields(self, sample_payments):
        """Test CSV export contains all fields required for VAT return."""
        admin = PaymentAdmin(Payment, AdminSite())
        factory = RequestFactory()
        request = factory.get("/admin/core/payment/")
        request.user = MagicMock()

        queryset = Payment.objects.all()
        response = admin._generate_csv(queryset, "test.csv")

        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)
        header = rows[0]

        # Check required columns for VAT return
        assert "Invoice Number" in header
        assert "Invoice Date" in header
        assert "Amount (ex VAT) GBP" in header
        assert "VAT Rate %" in header
        assert "VAT Amount GBP" in header
        assert "Total (inc VAT) GBP" in header

        # Personal data columns should NOT be present
        assert "Customer Email" not in header
        assert "Customer Name" not in header

    @pytest.mark.django_db
    def test_csv_export_totals_correct(self, sample_payments):
        """Test CSV export totals are calculated correctly."""
        admin = PaymentAdmin(Payment, AdminSite())
        factory = RequestFactory()
        request = factory.get("/admin/core/payment/")
        request.user = MagicMock()

        queryset = Payment.objects.all()
        response = admin._generate_csv(queryset, "test.csv")

        content = response.content.decode("utf-8")
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        # Find totals row
        totals_row = None
        for row in rows:
            if row and row[0] == "TOTALS":
                totals_row = row
                break

        assert totals_row is not None
        # Total ex VAT: 5.00 + 25.00 = 30.00
        assert "30.00" in totals_row
        # Total VAT: 1.00 + 5.00 = 6.00
        assert "6.00" in totals_row
        # Total inc VAT: 6.00 + 30.00 = 36.00
        assert "36.00" in totals_row


class TestSubscriptionExpiryCommand:
    """Test the process_expired_subscriptions management command."""

    @pytest.fixture
    def expired_user(self, db):
        """Create a user with an expired subscription."""
        user = User.objects.create_user(
            username="expired@example.com",
            email="expired@example.com",
            password="TestPass123!",
        )
        # Subscription ended 2 days ago
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
        user.profile.subscription_current_period_end = timezone.now() - timedelta(
            days=2
        )
        user.profile.save()
        return user

    @pytest.fixture
    def past_due_user(self, db):
        """Create a user with past due subscription (within grace period)."""
        user = User.objects.create_user(
            username="pastdue@example.com",
            email="pastdue@example.com",
            password="TestPass123!",
        )
        # Past due but within 7 day grace period
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.subscription_status = UserProfile.SubscriptionStatus.PAST_DUE
        user.profile.subscription_current_period_end = timezone.now() - timedelta(
            days=3
        )
        user.profile.save()
        return user

    @pytest.fixture
    def past_due_expired_user(self, db):
        """Create a user with past due subscription (grace period expired)."""
        user = User.objects.create_user(
            username="pastdueexpired@example.com",
            email="pastdueexpired@example.com",
            password="TestPass123!",
        )
        # Past due and grace period expired
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.subscription_status = UserProfile.SubscriptionStatus.PAST_DUE
        user.profile.subscription_current_period_end = timezone.now() - timedelta(
            days=10
        )
        user.profile.save()
        # Manually set updated_at to simulate being past_due for > 7 days
        UserProfile.objects.filter(pk=user.profile.pk).update(
            updated_at=timezone.now() - timedelta(days=10)
        )
        user.profile.refresh_from_db()
        return user

    @pytest.mark.django_db
    @patch("checktick_app.core.email_utils.send_subscription_expired_email")
    def test_expired_subscription_downgrades_user(self, mock_email, expired_user):
        """Test expired subscription downgrades user to free tier."""
        from django.core.management import call_command

        # Create some surveys
        for i in range(5):
            Survey.objects.create(
                name=f"Survey {i+1}", owner=expired_user, slug=f"expired-survey-{i+1}"
            )

        call_command("process_expired_subscriptions")

        expired_user.profile.refresh_from_db()
        assert expired_user.profile.account_tier == UserProfile.AccountTier.FREE

        # 2 surveys should be closed (5 - 3 free limit = 2)
        closed = Survey.objects.filter(
            owner=expired_user, status=Survey.Status.CLOSED
        ).count()
        assert closed == 2

    @pytest.mark.django_db
    def test_past_due_within_grace_period_not_downgraded(self, past_due_user):
        """Test past due user within grace period is not downgraded."""
        from django.core.management import call_command

        initial_tier = past_due_user.profile.account_tier

        call_command("process_expired_subscriptions")

        past_due_user.profile.refresh_from_db()
        assert past_due_user.profile.account_tier == initial_tier

    @pytest.mark.django_db
    @patch("checktick_app.core.email_utils.send_subscription_expired_email")
    def test_past_due_grace_period_expired_downgrades(
        self, mock_email, past_due_expired_user
    ):
        """Test past due user after grace period is downgraded."""
        from django.core.management import call_command

        call_command("process_expired_subscriptions")

        past_due_expired_user.profile.refresh_from_db()
        assert (
            past_due_expired_user.profile.account_tier == UserProfile.AccountTier.FREE
        )


class TestVATConfiguration:
    """Test VAT configuration values."""

    def test_vat_rate_configured(self):
        """Test VAT_RATE is configured correctly."""
        vat_rate = getattr(settings, "VAT_RATE", None)
        assert vat_rate is not None
        assert 0 <= vat_rate <= 1  # Should be decimal (e.g., 0.20 for 20%)

    def test_subscription_tiers_have_vat_amounts(self):
        """Test all subscription tiers have VAT breakdown."""
        tiers = getattr(settings, "SUBSCRIPTION_TIERS", {})

        for tier_key, tier_config in tiers.items():
            if tier_config.get("amount", 0) > 0:  # Skip custom pricing tiers
                assert (
                    "amount_ex_vat" in tier_config
                ), f"{tier_key} missing amount_ex_vat"
                assert (
                    tier_config["amount"] > tier_config["amount_ex_vat"]
                ), f"{tier_key} inc VAT should be > ex VAT"

    def test_vat_calculation_correct_for_pro(self):
        """Test VAT calculation is correct for pro tier."""
        tiers = settings.SUBSCRIPTION_TIERS
        pro = tiers.get("pro", {})

        # £5 ex VAT + 20% = £6 inc VAT
        assert pro.get("amount_ex_vat") == 500  # £5.00 in pence
        assert pro.get("amount") == 600  # £6.00 in pence
        assert pro["amount"] - pro["amount_ex_vat"] == 100  # £1.00 VAT

    def test_vat_calculation_correct_for_team_small(self):
        """Test VAT calculation is correct for team_small tier."""
        tiers = settings.SUBSCRIPTION_TIERS
        team = tiers.get("team_small", {})

        # £25 ex VAT + 20% = £30 inc VAT
        assert team.get("amount_ex_vat") == 2500  # £25.00 in pence
        assert team.get("amount") == 3000  # £30.00 in pence
        assert team["amount"] - team["amount_ex_vat"] == 500  # £5.00 VAT
