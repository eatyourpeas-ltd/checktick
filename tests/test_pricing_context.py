"""Tests for the public pricing context and billing cycle display."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.models import Promotion
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


class TestPromotionPricingDisplay:
    """Promotion-driven price display on the public pricing page."""

    def _create_platform_promotion(self, **kwargs):
        defaults = dict(
            name="Half Price Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=Decimal("50.00"),
            is_active=True,
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=180),
        )
        defaults.update(kwargs)
        return Promotion.objects.create(**defaults)

    @pytest.mark.django_db
    def test_percent_promotion_builds_pricing_for_paid_tiers(self):
        """Paid tiers get strike-through pricing; maths matches the resolver."""
        if float(settings.VAT_RATE) != 0.20:
            pytest.skip("pricing expectations assume VAT_RATE=0.20")
        self._create_platform_promotion()
        ctx = _get_public_pricing_context()

        pro = ctx["promotions_by_tier"]["pro"]
        assert pro["pricing"]["monthly"]["original"] == "£24"
        assert pro["pricing"]["monthly"]["discounted"] == "£12"
        assert pro["pricing"]["annual"]["discounted"] == "£115.20"
        assert 5 <= pro["pricing"]["months_left"] <= 6
        assert "mths left" in pro["promo_note"]

    @pytest.mark.django_db
    def test_free_tier_excluded_from_promotions(self):
        """Free is free: no promotion should be signposted against it."""
        self._create_platform_promotion()
        ctx = _get_public_pricing_context()
        assert ctx["promotions_by_tier"]["free"] is None

    @pytest.mark.django_db
    def test_tier_override_has_no_pricing(self):
        """Tier overrides keep the note-only display (no strike-through price)."""
        self._create_platform_promotion(
            effect_type=Promotion.EffectType.TIER_OVERRIDE,
            effect_tier="team_small",
        )
        ctx = _get_public_pricing_context()
        pro = ctx["promotions_by_tier"]["pro"]
        assert pro["pricing"] is None
        assert pro["promo_note"] == pro["short_text"]

    @pytest.mark.django_db
    def test_open_ended_promotion_has_no_months_text(self):
        """Open-ended promotions show the offer without a months-left suffix."""
        self._create_platform_promotion(ends_at=None)
        ctx = _get_public_pricing_context()
        pro = ctx["promotions_by_tier"]["pro"]
        assert pro["pricing"]["months_left"] is None
        assert pro["promo_note"] == "50% off"

    @pytest.mark.django_db
    def test_pricing_page_renders_strike_and_months(self, client):
        """The pricing page shows the struck-through price and months left."""
        self._create_platform_promotion()
        response = client.get(reverse("core:pricing"))

        assert response.status_code == 200
        html = response.content.decode()
        assert "line-through" in html
        assert "mths left" in html
        assert "pro-price-original" in html
