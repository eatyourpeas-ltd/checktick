"""Payment processing integration for CheckTick using GoCardless.

This module provides a unified interface for interacting with the GoCardless API
for subscription management via Direct Debit.

GoCardless flow:
1. Create a Redirect Flow (customer authorises Direct Debit mandate)
2. Complete Redirect Flow (get customer and mandate IDs)
3. Create Subscription against the mandate

Automatically uses sandbox in DEBUG mode and production otherwise.
"""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
import requests

logger = logging.getLogger(__name__)
User = get_user_model()


class PaymentAPIError(Exception):
    """Exception raised for payment processor API errors."""

    pass


class PaymentClient:
    """Client for interacting with GoCardless API.

    Automatically configured based on DEBUG setting:
    - DEBUG=True: Uses sandbox environment
    - DEBUG=False: Uses production environment

    Reference: https://developer.gocardless.com/api-reference
    """

    def __init__(self):
        """Initialize payment client with environment-specific configuration."""
        self.api_key = settings.PAYMENT_API_KEY
        self.base_url = settings.PAYMENT_BASE_URL
        self.environment = settings.PAYMENT_ENVIRONMENT

        if not self.api_key:
            logger.warning(
                f"Payment API key not configured for {self.environment} environment"
            )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make a request to GoCardless API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/redirect_flows')
            data: Request body data
            params: Query parameters

        Returns:
            API response as dictionary

        Raises:
            PaymentAPIError: If API request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "GoCardless-Version": "2015-07-06",  # API version
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text
            logger.error(
                f"GoCardless API error ({self.environment}): {e.response.status_code} - {error_detail}"
            )
            raise PaymentAPIError(
                f"GoCardless API request failed: {e.response.status_code} - {error_detail}"
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"GoCardless API request exception ({self.environment}): {e}")
            raise PaymentAPIError(f"GoCardless API request failed: {str(e)}") from e

    # =========================================================================
    # Redirect Flow Methods (for setting up Direct Debit mandates)
    # =========================================================================

    def create_redirect_flow(
        self,
        description: str,
        session_token: str,
        success_redirect_url: str,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> dict:
        """Create a redirect flow to collect customer bank details.

        This starts the process of setting up a Direct Debit mandate.
        The customer is redirected to GoCardless to enter their bank details.

        Args:
            description: Description shown to customer during authorisation
            session_token: Unique token to identify this flow (e.g., user session ID)
            success_redirect_url: URL to redirect after successful authorisation
            user_email: Pre-fill customer email (optional)
            user_name: Pre-fill customer name (optional)

        Returns:
            Redirect flow data including redirect_url

        Reference: https://developer.gocardless.com/api-reference/#redirect-flows-create-a-redirect-flow
        """
        data = {
            "redirect_flows": {
                "description": description,
                "session_token": session_token,
                "success_redirect_url": success_redirect_url,
                "scheme": "bacs",  # UK Direct Debit
            }
        }

        # Pre-fill customer details if provided
        if user_email or user_name:
            data["redirect_flows"]["prefilled_customer"] = {}
            if user_email:
                data["redirect_flows"]["prefilled_customer"]["email"] = user_email
            if user_name:
                data["redirect_flows"]["prefilled_customer"]["given_name"] = (
                    user_name.split()[0] if user_name else ""
                )
                if len(user_name.split()) > 1:
                    data["redirect_flows"]["prefilled_customer"]["family_name"] = (
                        " ".join(user_name.split()[1:])
                    )

        logger.info(f"Creating redirect flow ({self.environment}): {description}")
        response = self._make_request("POST", "/redirect_flows", data=data)
        redirect_flow = response.get("redirect_flows", {})
        logger.info(
            f"Redirect flow created ({self.environment}): {redirect_flow.get('id')}"
        )
        return redirect_flow

    def complete_redirect_flow(self, redirect_flow_id: str, session_token: str) -> dict:
        """Complete a redirect flow after customer authorisation.

        Call this after the customer returns from the redirect URL.
        This creates the customer and mandate in GoCardless.

        Args:
            redirect_flow_id: The redirect flow ID from the URL parameter
            session_token: The same session token used when creating the flow

        Returns:
            Completed redirect flow with customer_id and mandate_id

        Reference: https://developer.gocardless.com/api-reference/#redirect-flows-complete-a-redirect-flow
        """
        data = {
            "data": {
                "session_token": session_token,
            }
        }

        logger.info(
            f"Completing redirect flow ({self.environment}): {redirect_flow_id}"
        )
        response = self._make_request(
            "POST", f"/redirect_flows/{redirect_flow_id}/actions/complete", data=data
        )
        redirect_flow = response.get("redirect_flows", {})
        logger.info(
            f"Redirect flow completed ({self.environment}): customer={redirect_flow.get('links', {}).get('customer')}, "
            f"mandate={redirect_flow.get('links', {}).get('mandate')}"
        )
        return redirect_flow

    # =========================================================================
    # Customer Methods
    # =========================================================================

    def get_customer(self, customer_id: str) -> dict:
        """Get customer details from GoCardless.

        Args:
            customer_id: GoCardless customer ID

        Returns:
            Customer data

        Reference: https://developer.gocardless.com/api-reference/#customers-get-a-single-customer
        """
        logger.info(f"Fetching customer ({self.environment}): {customer_id}")
        response = self._make_request("GET", f"/customers/{customer_id}")
        return response.get("customers", {})

    def update_customer(self, customer_id: str, **kwargs) -> dict:
        """Update customer details in GoCardless.

        Args:
            customer_id: GoCardless customer ID
            **kwargs: Fields to update (email, given_name, family_name, etc.)

        Returns:
            Updated customer data

        Reference: https://developer.gocardless.com/api-reference/#customers-update-a-customer
        """
        data = {"customers": kwargs}
        logger.info(f"Updating customer ({self.environment}): {customer_id}")
        response = self._make_request("PUT", f"/customers/{customer_id}", data=data)
        return response.get("customers", {})

    # =========================================================================
    # Mandate Methods
    # =========================================================================

    def get_mandate(self, mandate_id: str) -> dict:
        """Get mandate details from GoCardless.

        Args:
            mandate_id: GoCardless mandate ID

        Returns:
            Mandate data

        Reference: https://developer.gocardless.com/api-reference/#mandates-get-a-single-mandate
        """
        logger.info(f"Fetching mandate ({self.environment}): {mandate_id}")
        response = self._make_request("GET", f"/mandates/{mandate_id}")
        return response.get("mandates", {})

    def cancel_mandate(self, mandate_id: str) -> dict:
        """Cancel a mandate.

        This will also cancel any associated subscriptions.

        Args:
            mandate_id: GoCardless mandate ID

        Returns:
            Cancelled mandate data

        Reference: https://developer.gocardless.com/api-reference/#mandates-cancel-a-mandate
        """
        logger.info(f"Cancelling mandate ({self.environment}): {mandate_id}")
        response = self._make_request("POST", f"/mandates/{mandate_id}/actions/cancel")
        return response.get("mandates", {})

    # =========================================================================
    # Subscription Methods
    # =========================================================================

    def create_subscription(
        self,
        mandate_id: str,
        amount: int,
        currency: str = "GBP",
        interval_unit: str = "monthly",
        interval: int = 1,
        name: Optional[str] = None,
        metadata: Optional[dict] = None,
        start_date: Optional[str] = None,
    ) -> dict:
        """Create a new subscription against a mandate.

        Unlike Paddle, GoCardless subscriptions are created with amount and
        interval directly, not via price IDs.

        Args:
            mandate_id: GoCardless mandate ID
            amount: Amount in minor units (e.g., 500 for £5.00)
            currency: Currency code (default: GBP)
            interval_unit: weekly, monthly, yearly
            interval: Number of interval_units between payments (default: 1)
            name: Name of the subscription (shown to customer)
            metadata: Custom metadata to store with subscription
            start_date: First payment date (YYYY-MM-DD), defaults to earliest possible

        Returns:
            Subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-create-a-subscription
        """
        data = {
            "subscriptions": {
                "amount": str(amount),
                "currency": currency,
                "interval_unit": interval_unit,
                "interval": interval,
                "links": {
                    "mandate": mandate_id,
                },
            }
        }

        if name:
            data["subscriptions"]["name"] = name
        if metadata:
            data["subscriptions"]["metadata"] = metadata
        if start_date:
            data["subscriptions"]["start_date"] = start_date

        logger.info(
            f"Creating subscription ({self.environment}): mandate={mandate_id}, "
            f"amount={amount} {currency}, interval={interval} {interval_unit}"
        )
        response = self._make_request("POST", "/subscriptions", data=data)
        subscription = response.get("subscriptions", {})
        logger.info(
            f"Subscription created ({self.environment}): {subscription.get('id')}"
        )
        return subscription

    def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details from GoCardless.

        Args:
            subscription_id: GoCardless subscription ID

        Returns:
            Subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-get-a-single-subscription
        """
        logger.info(f"Fetching subscription ({self.environment}): {subscription_id}")
        response = self._make_request("GET", f"/subscriptions/{subscription_id}")
        return response.get("subscriptions", {})

    def cancel_subscription(self, subscription_id: str) -> dict:
        """Cancel a subscription.

        Args:
            subscription_id: GoCardless subscription ID

        Returns:
            Cancelled subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-cancel-a-subscription
        """
        logger.info(f"Cancelling subscription ({self.environment}): {subscription_id}")
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/actions/cancel"
        )
        return response.get("subscriptions", {})

    def pause_subscription(self, subscription_id: str) -> dict:
        """Pause a subscription.

        Args:
            subscription_id: GoCardless subscription ID

        Returns:
            Paused subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-pause-a-subscription
        """
        logger.info(f"Pausing subscription ({self.environment}): {subscription_id}")
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/actions/pause"
        )
        return response.get("subscriptions", {})

    def resume_subscription(self, subscription_id: str) -> dict:
        """Resume a paused subscription.

        Args:
            subscription_id: GoCardless subscription ID

        Returns:
            Resumed subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-resume-a-subscription
        """
        logger.info(f"Resuming subscription ({self.environment}): {subscription_id}")
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/actions/resume"
        )
        return response.get("subscriptions", {})

    def update_subscription(
        self,
        subscription_id: str,
        amount: Optional[int] = None,
        name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Update a subscription.

        Args:
            subscription_id: GoCardless subscription ID
            amount: New amount in minor units (optional)
            name: New name (optional)
            metadata: New metadata (optional)

        Returns:
            Updated subscription data

        Reference: https://developer.gocardless.com/api-reference/#subscriptions-update-a-subscription
        """
        data = {"subscriptions": {}}
        if amount is not None:
            data["subscriptions"]["amount"] = str(amount)
        if name is not None:
            data["subscriptions"]["name"] = name
        if metadata is not None:
            data["subscriptions"]["metadata"] = metadata

        logger.info(f"Updating subscription ({self.environment}): {subscription_id}")
        response = self._make_request(
            "PUT", f"/subscriptions/{subscription_id}", data=data
        )
        return response.get("subscriptions", {})

    # =========================================================================
    # Payment Methods
    # =========================================================================

    def list_payments(
        self,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """List payments, optionally filtered by customer or subscription.

        Args:
            customer_id: Filter by customer ID (optional)
            subscription_id: Filter by subscription ID (optional)
            limit: Maximum number of payments to return (default: 50)

        Returns:
            List of payment records

        Reference: https://developer.gocardless.com/api-reference/#payments-list-payments
        """
        params = {"limit": limit}
        if customer_id:
            params["customer"] = customer_id
        if subscription_id:
            params["subscription"] = subscription_id

        logger.info(
            f"Listing payments ({self.environment}): customer={customer_id}, subscription={subscription_id}"
        )
        response = self._make_request("GET", "/payments", params=params)
        return response.get("payments", [])

    def get_payment(self, payment_id: str) -> dict:
        """Get a single payment's details.

        Args:
            payment_id: GoCardless payment ID

        Returns:
            Payment data

        Reference: https://developer.gocardless.com/api-reference/#payments-get-a-single-payment
        """
        logger.info(f"Fetching payment ({self.environment}): {payment_id}")
        response = self._make_request("GET", f"/payments/{payment_id}")
        return response.get("payments", {})


# Global client instance
payment_client = PaymentClient()


def get_or_create_redirect_flow(
    user, tier: str, success_url: str, session_token: str
) -> str:
    """Create a redirect flow for a user to set up Direct Debit.

    Args:
        user: Django User instance
        tier: The subscription tier being purchased
        success_url: URL to redirect after successful authorisation
        session_token: Unique session token for this flow

    Returns:
        Redirect URL for the user to authorise Direct Debit

    Raises:
        PaymentAPIError: If redirect flow creation fails
    """
    tier_config = settings.SUBSCRIPTION_TIERS.get(tier, {})
    tier_name = tier_config.get("name", tier.replace("_", " ").title())

    redirect_flow = payment_client.create_redirect_flow(
        description=f"CheckTick {tier_name} Subscription",
        session_token=session_token,
        success_redirect_url=success_url,
        user_email=user.email,
        user_name=user.get_full_name() or user.username,
    )

    logger.info(
        f"Created redirect flow for user {user.username}: {redirect_flow.get('id')}"
    )
    return redirect_flow.get("redirect_url", "")


def complete_mandate_setup(
    user, redirect_flow_id: str, session_token: str
) -> tuple[str, str]:
    """Complete the mandate setup after user authorisation.

    Args:
        user: Django User instance
        redirect_flow_id: The redirect flow ID from the return URL
        session_token: The same session token used when creating the flow

    Returns:
        Tuple of (customer_id, mandate_id)

    Raises:
        PaymentAPIError: If completion fails
    """
    redirect_flow = payment_client.complete_redirect_flow(
        redirect_flow_id, session_token
    )

    links = redirect_flow.get("links", {})
    customer_id = links.get("customer", "")
    mandate_id = links.get("mandate", "")

    # Store in user profile
    profile = user.profile
    profile.payment_provider = "gocardless"
    profile.payment_customer_id = customer_id
    profile.payment_mandate_id = mandate_id
    profile.save(
        update_fields=[
            "payment_provider",
            "payment_customer_id",
            "payment_mandate_id",
            "updated_at",
        ]
    )

    logger.info(
        f"Mandate setup completed for user {user.username}: "
        f"customer={customer_id}, mandate={mandate_id}"
    )

    return customer_id, mandate_id


def create_subscription_for_user(user, tier: str, mandate_id: str) -> str:
    """Create a subscription for a user.

    Args:
        user: Django User instance
        tier: The subscription tier (must match key in SUBSCRIPTION_TIERS)
        mandate_id: The GoCardless mandate ID

    Returns:
        Subscription ID

    Raises:
        PaymentAPIError: If subscription creation fails
        ValueError: If tier is not configured
    """
    tier_config = settings.SUBSCRIPTION_TIERS.get(tier)
    if not tier_config:
        raise ValueError(f"Unknown subscription tier: {tier}")

    subscription = payment_client.create_subscription(
        mandate_id=mandate_id,
        amount=tier_config["amount"],
        currency=tier_config.get("currency", "GBP"),
        interval_unit=tier_config.get("interval_unit", "monthly"),
        interval=tier_config.get("interval", 1),
        name=tier_config.get("name", f"CheckTick {tier.title()} Plan"),
        metadata={
            "user_id": str(user.id),
            "username": user.username,
            "tier": tier,
        },
    )

    subscription_id = subscription.get("id", "")

    # Update user profile
    profile = user.profile
    profile.payment_subscription_id = subscription_id
    profile.subscription_status = "pending"  # Will become active via webhook
    profile.account_tier = tier
    profile.tier_changed_at = (
        settings.timezone.now() if hasattr(settings, "timezone") else None
    )
    profile.save(
        update_fields=[
            "payment_subscription_id",
            "subscription_status",
            "account_tier",
            "tier_changed_at",
            "updated_at",
        ]
    )

    logger.info(
        f"Created subscription for user {user.username}: {subscription_id} (tier: {tier})"
    )

    return subscription_id
