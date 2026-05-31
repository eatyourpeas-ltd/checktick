"""Tests for pricing overrides and effective tier rendering."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.core.models import PricingOverride, Promotion


@pytest.mark.django_db
class TestPricingOverrides:
    """Test pricing override merge behavior and UI rendering."""

    def test_get_effective_tiers_uses_active_override(self):
        """Active override should replace settings values for that tier."""
        PricingOverride.objects.create(
            tier="pro",
            amount=700,
            amount_ex_vat=583,
            is_active=True,
        )

        effective = PricingOverride.get_effective_tiers()
        assert effective["pro"]["amount"] == 700
        assert effective["pro"]["amount_ex_vat"] == 583

    def test_get_effective_tiers_ignores_inactive_override(self):
        """Inactive override should not change effective tier values."""
        effective_before = PricingOverride.get_effective_tiers()
        baseline_amount = effective_before["pro"]["amount"]
        baseline_ex_vat = effective_before["pro"]["amount_ex_vat"]

        PricingOverride.objects.create(
            tier="pro",
            amount=700,
            amount_ex_vat=583,
            is_active=False,
        )

        effective_after = PricingOverride.get_effective_tiers()
        assert effective_after["pro"]["amount"] == baseline_amount
        assert effective_after["pro"]["amount_ex_vat"] == baseline_ex_vat

    def test_public_pricing_page_shows_override_amount(self, client):
        """Public pricing page should render override amount for Pro tier."""
        PricingOverride.objects.create(
            tier="pro",
            amount=700,
            amount_ex_vat=583,
            is_active=True,
        )

        response = client.get(reverse("core:pricing"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "£7" in content

    def test_public_pricing_page_shows_active_platform_promotion(self, client):
        """Pricing page should show active platform-level promotion signpost."""
        Promotion.objects.create(
            name="Spring Offer",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            ends_at=timezone.now() + timedelta(days=14),
            is_active=True,
        )

        response = client.get(reverse("core:pricing"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Active offers" in content
        assert "10% off" in content

    def test_signup_page_shows_tier_or_platform_promotion(self, client):
        """Signup should surface active promotions in tier choices."""
        Promotion.objects.create(
            name="Pro Welcome",
            scope_type=Promotion.ScopeType.TIER,
            target_tier="pro",
            effect_type=Promotion.EffectType.FIXED_DISCOUNT,
            effect_value=2,
            is_active=True,
        )

        response = client.get(reverse("core:signup"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "£2 off" in content

    def test_homepage_shows_unobtrusive_promotion_signpost(self, client):
        """Home page should include subtle pricing signpost when promotions are active."""
        Promotion.objects.create(
            name="Team Boost",
            scope_type=Promotion.ScopeType.TIER,
            target_tier="team_small",
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=15,
            is_active=True,
        )

        response = client.get(reverse("core:home"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Limited-time offer" in content
        assert "15% off" in content
