"""Tests for organisation checkout views and access control.

Tests focus on:
1. Access control - only valid tokens can access views
2. Security guards - expired, completed, inactive organisations
3. Checkout workflow - start, redirect, complete
4. Session security - session token validation
5. SELF_HOSTED mode - billing disabled
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import Organization

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def organisation_pending_setup(db):
    """Create an organisation pending checkout setup."""
    org = Organization.objects.create(
        name="Test Organisation Ltd",
        billing_type=Organization.BillingType.PER_SEAT,
        max_seats=10,
        price_per_seat=Decimal("5.00"),
        billing_contact_email="billing@testorg.com",
        is_active=True,
        setup_token=uuid.uuid4().hex,
        setup_expires_at=timezone.now() + timedelta(days=30),
    )
    return org


@pytest.fixture
def organisation_setup_expired(db):
    """Create an organisation with expired setup token."""
    org = Organization.objects.create(
        name="Expired Setup Ltd",
        billing_type=Organization.BillingType.PER_SEAT,
        max_seats=5,
        price_per_seat=Decimal("5.00"),
        billing_contact_email="expired@test.com",
        is_active=True,
        setup_token=uuid.uuid4().hex,
        # Token expired 1 day ago
        setup_expires_at=timezone.now() - timedelta(days=1),
    )
    return org


@pytest.fixture
def organisation_setup_completed(db):
    """Create an organisation that has completed setup."""
    org = Organization.objects.create(
        name="Completed Setup Ltd",
        billing_type=Organization.BillingType.PER_SEAT,
        max_seats=5,
        price_per_seat=Decimal("5.00"),
        billing_contact_email="done@test.com",
        is_active=True,
        setup_token=uuid.uuid4().hex,
        setup_expires_at=timezone.now() + timedelta(days=30),
        setup_completed_at=timezone.now(),
        payment_customer_id="CU001",
        payment_subscription_id="SU001",
    )
    return org


@pytest.fixture
def organisation_inactive(db):
    """Create an inactive organisation."""
    org = Organization.objects.create(
        name="Inactive Ltd",
        billing_type=Organization.BillingType.PER_SEAT,
        max_seats=5,
        price_per_seat=Decimal("5.00"),
        billing_contact_email="inactive@test.com",
        is_active=False,
        setup_token=uuid.uuid4().hex,
        setup_expires_at=timezone.now() + timedelta(days=30),
    )
    return org


@pytest.fixture
def flat_rate_organisation(db):
    """Create a flat-rate billing organisation."""
    org = Organization.objects.create(
        name="Flat Rate Ltd",
        billing_type=Organization.BillingType.FLAT_RATE,
        flat_rate_price=Decimal("100.00"),
        billing_contact_email="flatrate@test.com",
        is_active=True,
        setup_token=uuid.uuid4().hex,
        setup_expires_at=timezone.now() + timedelta(days=30),
    )
    return org


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


# ============================================================================
# Access Control Tests - organisation_checkout (GET)
# ============================================================================


class TestOrganisationCheckoutAccessControl:
    """Test access control for the checkout display page."""

    @pytest.mark.django_db
    def test_valid_token_shows_checkout_page(self, client, organisation_pending_setup):
        """Valid token should display the checkout page."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert b"Complete Your Subscription" in response.content
        assert organisation_pending_setup.name.encode() in response.content

    @pytest.mark.django_db
    def test_invalid_token_redirects_with_error(self, client):
        """Invalid token should redirect with error message (not 404 for security)."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": "invalid_token_12345"},
        )
        response = client.get(url)

        # Should redirect to home with error (not 404 - don't reveal token existence)
        assert response.status_code == 302
        assert response.url == reverse("core:home")
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert (
            "invalid" in str(messages[0]).lower()
            or "expired" in str(messages[0]).lower()
        )

    @pytest.mark.django_db
    def test_expired_token_redirects_with_error(
        self, client, organisation_setup_expired
    ):
        """Expired setup token should redirect with error message."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_setup_expired.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 302
        # Should redirect to home
        assert response.url == reverse("core:home")
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "expired" in str(messages[0]).lower()

    @pytest.mark.django_db
    def test_completed_setup_redirects_to_login(
        self, client, organisation_setup_completed
    ):
        """Already completed setup should redirect to login."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_setup_completed.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 302
        assert response.url == reverse("login")
        # Check message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "already" in str(messages[0]).lower()

    @pytest.mark.django_db
    def test_inactive_organisation_redirects_with_error(
        self, client, organisation_inactive
    ):
        """Inactive organisation should redirect with error (not reveal existence)."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_inactive.setup_token},
        )
        response = client.get(url)

        # Should redirect to home (appears same as invalid token)
        assert response.status_code == 302
        assert response.url == reverse("core:home")

    @pytest.mark.django_db
    @override_settings(SELF_HOSTED=True)
    def test_self_hosted_mode_blocks_access(self, client, organisation_pending_setup):
        """SELF_HOSTED mode should block checkout access."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 302
        # Should redirect to home
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "not available" in str(messages[0]).lower()


# ============================================================================
# Access Control Tests - organisation_start_checkout (POST)
# ============================================================================


class TestOrganisationStartCheckoutAccessControl:
    """Test access control for starting checkout (POST to GoCardless)."""

    @pytest.mark.django_db
    def test_get_request_not_allowed(self, client, organisation_pending_setup):
        """GET request should return 405 (method not allowed)."""
        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 405

    @pytest.mark.django_db
    def test_invalid_token_redirects_with_error(self, client):
        """Invalid token should redirect with error (not 404 for security)."""
        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": "invalid_token_12345"},
        )
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse("core:home")

    @pytest.mark.django_db
    def test_expired_token_redirects(self, client, organisation_setup_expired):
        """Expired token should redirect with error."""
        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_setup_expired.setup_token},
        )
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse("core:home")

    @pytest.mark.django_db
    def test_completed_setup_redirects(self, client, organisation_setup_completed):
        """Completed setup should redirect to login."""
        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_setup_completed.setup_token},
        )
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse("login")

    @pytest.mark.django_db
    @override_settings(SELF_HOSTED=True)
    def test_self_hosted_blocks_start_checkout(
        self, client, organisation_pending_setup
    ):
        """SELF_HOSTED mode should block start checkout."""
        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.post(url)

        assert response.status_code == 302


# ============================================================================
# Access Control Tests - organisation_checkout_complete (GET)
# ============================================================================


class TestOrganisationCheckoutCompleteAccessControl:
    """Test access control for completing checkout (return from GoCardless)."""

    @pytest.mark.django_db
    def test_invalid_token_returns_404(self, client):
        """Invalid token should return 404."""
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": "invalid_token_12345"},
        )
        response = client.get(url)

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_missing_redirect_flow_id_redirects(
        self, client, organisation_pending_setup
    ):
        """Missing redirect_flow_id should redirect back to checkout."""
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url)

        assert response.status_code == 302
        expected_url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        assert response.url == expected_url
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "invalid" in str(messages[0]).lower()

    @pytest.mark.django_db
    def test_invalid_session_redirects(self, client, organisation_pending_setup):
        """Invalid session should redirect back to checkout."""
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url, {"redirect_flow_id": "RF0001"})

        assert response.status_code == 302
        expected_url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        assert response.url == expected_url
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "session" in str(messages[0]).lower()

    @pytest.mark.django_db
    def test_completed_setup_redirects_to_login(
        self, client, organisation_setup_completed
    ):
        """Already completed setup should redirect to login."""
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_setup_completed.setup_token},
        )
        response = client.get(url, {"redirect_flow_id": "RF0001"})

        assert response.status_code == 302
        assert response.url == reverse("login")

    @pytest.mark.django_db
    @override_settings(SELF_HOSTED=True)
    def test_self_hosted_blocks_complete(self, client, organisation_pending_setup):
        """SELF_HOSTED mode should block checkout completion."""
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        # Set up session
        session = client.session
        session["org_checkout_session_token"] = "test_session"
        session["org_checkout_org_id"] = organisation_pending_setup.id
        session.save()

        response = client.get(url, {"redirect_flow_id": "RF0001"})

        assert response.status_code == 302


# ============================================================================
# Checkout Workflow Tests
# ============================================================================


class TestCheckoutWorkflow:
    """Test the complete checkout workflow."""

    @pytest.mark.django_db
    def test_checkout_page_shows_per_seat_pricing(
        self, client, organisation_pending_setup
    ):
        """Checkout page should show per-seat pricing correctly."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url)

        content = response.content.decode()
        # Should show organisation name
        assert organisation_pending_setup.name in content
        # Should show billing type
        assert "Per Seat" in content or "per seat" in content.lower()
        # Should show number of seats
        assert "10" in content  # max_seats
        # Should show price (£5 per seat)
        assert "5.00" in content

    @pytest.mark.django_db
    def test_checkout_page_shows_flat_rate_pricing(
        self, client, flat_rate_organisation
    ):
        """Checkout page should show flat-rate pricing correctly."""
        url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": flat_rate_organisation.setup_token},
        )
        response = client.get(url)

        content = response.content.decode()
        assert flat_rate_organisation.name in content
        assert "Flat Rate" in content or "flat rate" in content.lower()
        # Should show price (£100)
        assert "100.00" in content

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_start_checkout_creates_redirect_flow(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """Starting checkout should create a GoCardless redirect flow."""
        mock_payment_client.create_redirect_flow.return_value = {
            "id": "RF0001234",
            "redirect_url": "https://pay.gocardless.com/flow/RF0001234",
        }

        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.post(url)

        # Should redirect to GoCardless
        assert response.status_code == 302
        # Validate redirect is to the exact GoCardless domain
        from urllib.parse import urlparse

        parsed_url = urlparse(response.url)
        # Check exact domain or subdomain (e.g., pay.gocardless.com)
        assert parsed_url.netloc == "gocardless.com" or parsed_url.netloc.endswith(".gocardless.com")

        # Verify redirect flow was created with correct params
        mock_payment_client.create_redirect_flow.assert_called_once()
        call_kwargs = mock_payment_client.create_redirect_flow.call_args.kwargs
        assert organisation_pending_setup.name in call_kwargs["description"]
        assert call_kwargs["user_email"] == "billing@testorg.com"

        # Organisation should have redirect_flow_id stored
        organisation_pending_setup.refresh_from_db()
        assert organisation_pending_setup.redirect_flow_id == "RF0001234"

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_start_checkout_sets_session(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """Starting checkout should set session tokens for security."""
        mock_payment_client.create_redirect_flow.return_value = {
            "id": "RF0001234",
            "redirect_url": "https://pay.gocardless.com/flow/RF0001234",
        }

        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        client.post(url)

        # Session should have checkout tokens
        session = client.session
        assert "org_checkout_session_token" in session
        assert session["org_checkout_org_id"] == organisation_pending_setup.id

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_complete_checkout_creates_subscription(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """Completing checkout should create subscription and activate org."""
        # Set up mock responses
        mock_payment_client.complete_redirect_flow.return_value = {
            "id": "RF0001234",
            "links": {
                "customer": "CU0001234",
                "mandate": "MD0001234",
            },
        }
        mock_payment_client.create_subscription.return_value = {
            "id": "SU0001234",
            "status": "active",
        }

        # Set up session (simulating start_checkout)
        session = client.session
        session["org_checkout_session_token"] = "test_session_token"
        session["org_checkout_org_id"] = organisation_pending_setup.id
        session.save()

        # Complete checkout
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(
            url,
            {"redirect_flow_id": "RF0001234"},
        )

        # Should redirect to login
        assert response.status_code == 302
        assert response.url == reverse("login")

        # Verify subscription was created
        mock_payment_client.complete_redirect_flow.assert_called_once_with(
            "RF0001234", "test_session_token"
        )
        mock_payment_client.create_subscription.assert_called_once()

        # Verify organisation was updated
        organisation_pending_setup.refresh_from_db()
        assert organisation_pending_setup.payment_customer_id == "CU0001234"
        assert organisation_pending_setup.payment_subscription_id == "SU0001234"
        assert organisation_pending_setup.setup_completed_at is not None

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "successfully" in str(messages[0]).lower()

        # Session should be cleared
        session = client.session
        assert "org_checkout_session_token" not in session
        assert "org_checkout_org_id" not in session

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_complete_checkout_calculates_correct_amount_per_seat(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """Checkout should calculate correct amount with VAT for per-seat billing."""
        mock_payment_client.complete_redirect_flow.return_value = {
            "id": "RF0001234",
            "links": {"customer": "CU001", "mandate": "MD001"},
        }
        mock_payment_client.create_subscription.return_value = {"id": "SU001"}

        # Set up session
        session = client.session
        session["org_checkout_session_token"] = "test_session"
        session["org_checkout_org_id"] = organisation_pending_setup.id
        session.save()

        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        client.get(url, {"redirect_flow_id": "RF0001234"})

        # Organisation has 10 seats at £5/seat = £50 ex VAT
        # £50 + 20% VAT = £60 inc VAT = 6000 pence
        call_kwargs = mock_payment_client.create_subscription.call_args.kwargs
        assert call_kwargs["amount"] == 6000  # 6000 pence
        assert call_kwargs["currency"] == "GBP"
        assert call_kwargs["interval_unit"] == "monthly"

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_complete_checkout_calculates_correct_amount_flat_rate(
        self, mock_payment_client, client, flat_rate_organisation
    ):
        """Checkout should calculate correct amount with VAT for flat-rate billing."""
        mock_payment_client.complete_redirect_flow.return_value = {
            "id": "RF0001234",
            "links": {"customer": "CU001", "mandate": "MD001"},
        }
        mock_payment_client.create_subscription.return_value = {"id": "SU001"}

        # Set up session
        session = client.session
        session["org_checkout_session_token"] = "test_session"
        session["org_checkout_org_id"] = flat_rate_organisation.id
        session.save()

        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": flat_rate_organisation.setup_token},
        )
        client.get(url, {"redirect_flow_id": "RF0001234"})

        # £100 flat rate + 20% VAT = £120 = 12000 pence
        call_kwargs = mock_payment_client.create_subscription.call_args.kwargs
        assert call_kwargs["amount"] == 12000  # 12000 pence


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestCheckoutErrorHandling:
    """Test error handling during checkout."""

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_start_checkout_handles_api_error(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """API errors during start checkout should show friendly error."""
        from checktick_app.core.billing import PaymentAPIError

        mock_payment_client.create_redirect_flow.side_effect = PaymentAPIError(
            "Connection failed"
        )

        url = reverse(
            "surveys:organisation_start_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.post(url)

        # Should redirect back to checkout page
        assert response.status_code == 302
        expected_url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        assert response.url == expected_url

        # Should show error message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "payment provider" in str(messages[0]).lower()

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_complete_checkout_handles_api_error(
        self, mock_payment_client, client, organisation_pending_setup
    ):
        """API errors during complete checkout should show friendly error."""
        from checktick_app.core.billing import PaymentAPIError

        mock_payment_client.complete_redirect_flow.side_effect = PaymentAPIError(
            "Mandate creation failed"
        )

        # Set up session
        session = client.session
        session["org_checkout_session_token"] = "test_session"
        session["org_checkout_org_id"] = organisation_pending_setup.id
        session.save()

        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url, {"redirect_flow_id": "RF0001234"})

        # Should redirect back to checkout page
        assert response.status_code == 302
        expected_url = reverse(
            "surveys:organisation_checkout",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        assert response.url == expected_url

        # Should show error message
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "contact support" in str(messages[0]).lower()


# ============================================================================
# Session Security Tests
# ============================================================================


class TestSessionSecurity:
    """Test session-based security measures."""

    @pytest.mark.django_db
    @patch("checktick_app.surveys.views_organisation_billing.payment_client")
    def test_wrong_org_session_rejected(
        self, mock_payment_client, client, organisation_pending_setup, db
    ):
        """Session with wrong org ID should be rejected."""
        # Create another organisation
        other_org = Organization.objects.create(
            name="Other Org",
            billing_type=Organization.BillingType.PER_SEAT,
            max_seats=5,
            price_per_seat=Decimal("5.00"),
            billing_contact_email="other@test.com",
            is_active=True,
            setup_token=uuid.uuid4().hex,
            setup_expires_at=timezone.now() + timedelta(days=30),
        )

        # Set session for wrong org
        session = client.session
        session["org_checkout_session_token"] = "test_session"
        session["org_checkout_org_id"] = other_org.id  # Wrong org!
        session.save()

        # Try to complete for different org
        url = reverse(
            "surveys:organisation_checkout_complete",
            kwargs={"token": organisation_pending_setup.setup_token},
        )
        response = client.get(url, {"redirect_flow_id": "RF0001234"})

        # Should redirect back with session error
        assert response.status_code == 302
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert "session" in str(messages[0]).lower()

        # GoCardless should not have been called
        mock_payment_client.complete_redirect_flow.assert_not_called()

    @pytest.mark.django_db
    def test_session_cleared_after_successful_completion(
        self, client, organisation_pending_setup
    ):
        """Session should be cleared after successful checkout."""
        with patch(
            "checktick_app.surveys.views_organisation_billing.payment_client"
        ) as mock:
            mock.complete_redirect_flow.return_value = {
                "id": "RF001",
                "links": {"customer": "CU001", "mandate": "MD001"},
            }
            mock.create_subscription.return_value = {"id": "SU001"}

            # Set up session
            session = client.session
            session["org_checkout_session_token"] = "test_session"
            session["org_checkout_org_id"] = organisation_pending_setup.id
            session.save()

            url = reverse(
                "surveys:organisation_checkout_complete",
                kwargs={"token": organisation_pending_setup.setup_token},
            )
            client.get(url, {"redirect_flow_id": "RF001"})

            # Session should be cleared
            session = client.session
            assert session.get("org_checkout_session_token") is None
            assert session.get("org_checkout_org_id") is None
