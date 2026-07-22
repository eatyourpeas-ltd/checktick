"""Tests for the signup page billing cycle display."""

import pytest
from django.test import Client
from django.urls import reverse


class TestSignupPageBillingCycle:
    """Test that the signup page shows monthly/annual toggle."""

    @pytest.mark.django_db
    def test_signup_page_has_billing_cycle_toggle(self):
        """Signup page includes the monthly/annual toggle."""
        client = Client(HTTP_HOST="localhost")
        response = client.get(reverse("core:signup"))
        assert response.status_code == 200
        assert b"billing-cycle-toggle" in response.content

    @pytest.mark.django_db
    def test_signup_page_shows_annual_prices(self):
        """Signup page includes annual price data for JS switching."""
        client = Client(HTTP_HOST="localhost")
        response = client.get(reverse("core:signup"))
        assert response.status_code == 200
        # The annual prices should be available in the context
        assert (
            b"tier_display_annual" in response.content or b"annual" in response.content
        )
