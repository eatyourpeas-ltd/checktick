"""Tests for pro-rata refunds on annual subscriptions."""

import pytest
from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from checktick_app.core.models import Payment, UserProfile

User = get_user_model()

TEST_PASSWORD = "TestPass123!"


@pytest.fixture
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(
        username="superadmin",
        email="superadmin@test.com",
        password=TEST_PASSWORD,
    )


class TestProRataRefunds:
    """Test pro-rata refund calculation for annual subscriptions.

    Per the refund policy (docs/refund-policy.md §4.5):
    - 14-day right to cancel for first-time subscribers (full refund)
    - After 14 days, pro-rated refunds may be considered for annual subscriptions
    """

    @pytest.fixture
    def annual_payment(self, db):
        """Create an annual Pro payment (£230.40 inc VAT)."""
        user = User.objects.create_user(
            username="annual-refund@example.com",
            email="annual-refund@example.com",
            password="TestPass123!",
        )
        user.profile.account_tier = UserProfile.AccountTier.PRO
        user.profile.payment_provider = "gocardless"
        user.profile.save()

        return Payment.objects.create(
            user=user,
            invoice_number="INV-ANNUAL-REFUND",
            invoice_date=date.today(),
            payment_provider="gocardless",
            payment_id="PM-ANNUAL-REFUND",
            subscription_id="SB-ANNUAL-REFUND",
            tier="pro",
            billing_cycle="annual",
            amount_ex_vat=19200,  # £192 ex VAT
            vat_amount=3840,  # £38.40 VAT
            amount_inc_vat=23040,  # £230.40 inc VAT
            vat_rate=0.20,
            customer_email=user.email,
            customer_name=user.username,
            status=Payment.PaymentStatus.CONFIRMED,
            confirmed_at=date.today(),
        )

    @pytest.mark.django_db
    def test_pro_rata_refund_calculation_half_year(self, annual_payment):
        """Pro-rata refund for half a year remaining = 50% of annual."""
        from checktick_app.core.pricing import compute_pro_rata_refund

        # 6 months into a 12-month annual subscription = 6 months remaining
        refund = compute_pro_rata_refund(
            annual_payment.amount_inc_vat,
            billing_cycle="annual",
            days_elapsed=182,  # ~6 months
            total_days=365,
        )
        # 183/365 remaining ≈ 50.1% → ~£115.50
        assert refund > 0
        assert refund < annual_payment.amount_inc_vat
        # Should be roughly half
        assert abs(refund - annual_payment.amount_inc_vat / 2) < 500  # within £5

    @pytest.mark.django_db
    def test_pro_rata_refund_full_year_remaining(self, annual_payment):
        """Pro-rata refund with full year remaining = full amount."""
        from checktick_app.core.pricing import compute_pro_rata_refund

        refund = compute_pro_rata_refund(
            annual_payment.amount_inc_vat,
            billing_cycle="annual",
            days_elapsed=0,
            total_days=365,
        )
        assert refund == annual_payment.amount_inc_vat

    @pytest.mark.django_db
    def test_pro_rata_refund_zero_remaining(self, annual_payment):
        """Pro-rata refund with no time remaining = 0."""
        from checktick_app.core.pricing import compute_pro_rata_refund

        refund = compute_pro_rata_refund(
            annual_payment.amount_inc_vat,
            billing_cycle="annual",
            days_elapsed=365,
            total_days=365,
        )
        assert refund == 0

    @pytest.mark.django_db
    def test_pro_rata_refund_monthly_returns_full(self, annual_payment):
        """Monthly subscriptions always refund the full amount (no pro-rata)."""
        from checktick_app.core.pricing import compute_pro_rata_refund

        refund = compute_pro_rata_refund(
            annual_payment.amount_inc_vat,
            billing_cycle="monthly",
            days_elapsed=15,
            total_days=30,
        )
        # Monthly = full refund (existing behaviour)
        assert refund == annual_payment.amount_inc_vat

    @pytest.mark.django_db
    def test_platform_admin_can_issue_pro_rata_refund(self, annual_payment, superuser):
        """Platform admin can issue a pro-rata refund for annual subscriptions."""

        client = Client()
        client.force_login(superuser)

        with patch(
            "checktick_app.core.views_platform_admin.PaymentClient"
        ) as mock_client:
            mock_client.return_value.refund_payment.return_value = {"id": "RF_TEST"}
            response = client.post(
                reverse("core:platform_admin_billing_refund", args=[annual_payment.id]),
                data={
                    "refund_reason_code": "other",
                    "refund_reason": "Annual pro-rata refund after 6 months",
                    "refund_amount_pence": str(annual_payment.amount_inc_vat // 2),
                    "mode": "platform",
                },
            )

        assert response.status_code == 302
        annual_payment.refresh_from_db()
        assert annual_payment.status == Payment.PaymentStatus.REFUNDED

    @pytest.mark.django_db
    def test_full_refund_still_works_for_annual(self, annual_payment, superuser):
        """Full refunds still work for annual (e.g. within 14-day window)."""

        client = Client()
        client.force_login(superuser)

        with patch(
            "checktick_app.core.views_platform_admin.PaymentClient"
        ) as mock_client:
            mock_client.return_value.refund_payment.return_value = {"id": "RF_FULL"}
            response = client.post(
                reverse("core:platform_admin_billing_refund", args=[annual_payment.id]),
                data={
                    "refund_reason_code": "support_goodwill",
                    "refund_reason": "Full refund within 14-day window",
                    "mode": "platform",
                },
            )

        assert response.status_code == 302
        annual_payment.refresh_from_db()
        assert annual_payment.status == Payment.PaymentStatus.REFUNDED
