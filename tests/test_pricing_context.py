"""Tests for the public pricing context and billing cycle display."""

import pytest
from django.conf import settings

from checktick_app.core.views import _get_public_pricing_context


class TestPublicPricingContext:
    """Test that _get_public_pricing_context provides monthly and annual prices."""

    @pytest.mark.django_db
    def test_context_includes_monthly_tier_display(self):
        """Context includes tier_display for monthly prices."""
        ctx = _get_public_pricing_context()
        assert "tier_display" in ctx
        # Pro monthly: £24 inc VAT at 20%
        if float(settings.VAT_RATE) == 0.20:
            assert ctx["tier_display"]["pro"] == "£24"

    @pytest.mark.django_db
    def test_context_includes_annual_tier_display(self):
        """Context includes annual tier_display with discounted prices."""
        ctx = _get_public_pricing_context()
        assert "tier_display_annual" in ctx
        # Pro annual: £20 × 12 × 0.80 = £192 ex VAT, £230.40 inc VAT at 20%
        if (
            float(settings.VAT_RATE) == 0.20
            and float(settings.ANNUAL_DISCOUNT_PERCENT) == 20
        ):
            assert ctx["tier_display_annual"]["pro"] == "£230.40"

    @pytest.mark.django_db
    def test_context_includes_annual_tier_pounds(self):
        """Context includes annual tier_pounds for JS price switching."""
        ctx = _get_public_pricing_context()
        assert "tier_pounds_annual" in ctx
        if (
            float(settings.VAT_RATE) == 0.20
            and float(settings.ANNUAL_DISCOUNT_PERCENT) == 20
        ):
            assert (
                ctx["tier_pounds_annual"]["pro"] == 230
            )  # £230.40 → 230 (int division)

    @pytest.mark.django_db
    def test_context_includes_annual_discount_percent(self):
        """Context includes the annual discount percentage for display."""
        ctx = _get_public_pricing_context()
        assert "annual_discount_percent" in ctx
        assert ctx["annual_discount_percent"] == float(settings.ANNUAL_DISCOUNT_PERCENT)

    @pytest.mark.django_db
    def test_context_monthly_tier_pounds_still_present(self):
        """Monthly tier_pounds is still present (backwards compat)."""
        ctx = _get_public_pricing_context()
        assert "tier_pounds" in ctx
        if float(settings.VAT_RATE) == 0.20:
            assert ctx["tier_pounds"]["pro"] == 24
