"""Tests for pricing overrides and effective tier rendering."""

from django.urls import reverse
import pytest

from checktick_app.core.models import PricingOverride


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
