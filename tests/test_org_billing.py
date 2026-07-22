"""Tests for organisation annual billing."""

import pytest
from django.conf import settings

from checktick_app.surveys.models import Organization


class TestOrganisationBillingCycle:
    """Test that Organisation supports annual billing with discount."""

    @pytest.mark.django_db
    def test_organization_has_billing_cycle_field(self, db):
        """Organisation.billing_cycle defaults to 'monthly'."""
        org = Organization.objects.create(name="Test Org")
        assert org.billing_cycle == "monthly"

    @pytest.mark.django_db
    def test_organization_can_be_annual(self, db):
        """Organisation.billing_cycle can be set to 'annual'."""
        org = Organization.objects.create(
            name="Annual Org",
            billing_cycle="annual",
            billing_type=Organization.BillingType.PER_SEAT,
            price_per_seat="20.00",
        )
        assert org.billing_cycle == "annual"

    @pytest.mark.django_db
    def test_organization_annual_per_seat_amount(self, db):
        """Annual per-seat amount = monthly × 12 × (1 - discount)."""
        from checktick_app.core.pricing import compute_annual_amount

        # £20/month per seat, 20% annual discount
        monthly_per_seat_pence = 2000
        annual = compute_annual_amount(monthly_per_seat_pence)
        # £20 × 12 × 0.80 = £192
        assert annual == 19200

    @pytest.mark.django_db
    def test_organization_annual_flat_rate_amount(self, db):
        """Annual flat-rate amount = monthly × 12 × (1 - discount)."""
        from checktick_app.core.pricing import compute_annual_amount

        # £500/month flat rate, 20% annual discount
        monthly_flat_pence = 50000
        annual = compute_annual_amount(monthly_flat_pence)
        # £500 × 12 × 0.80 = £4,800
        assert annual == 480000

    @pytest.mark.django_db
    def test_organization_monthly_amount_unchanged(self, db):
        """compute_annual_amount with 0% discount = monthly × 12."""
        from checktick_app.core.pricing import compute_annual_amount

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(settings, "ANNUAL_DISCOUNT_PERCENT", 0)
            annual = compute_annual_amount(2000)
            assert annual == 24000  # £20 × 12, no discount
