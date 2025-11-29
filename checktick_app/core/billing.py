"""Payment processing integration for CheckTick.

This module provides a unified interface for interacting with the payment processor API
for subscription management, customer creation, and webhook handling.

Currently implements Paddle as the payment processor.
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
    """Client for interacting with payment processor API.

    Currently implements Paddle as the payment processor.
    Automatically configured based on DEBUG setting:
    - DEBUG=True: Uses sandbox environment
    - DEBUG=False: Uses production environment
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
        """Make a request to Paddle API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., '/customers')
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
                f"Payment API error ({self.environment}): {e.response.status_code} - {error_detail}"
            )
            raise PaymentAPIError(
                f"Payment API request failed: {e.response.status_code} - {error_detail}"
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Payment API request exception ({self.environment}): {e}")
            raise PaymentAPIError(f"Payment API request failed: {str(e)}") from e

    def create_customer(
        self, email: str, name: str = "", custom_data: Optional[dict] = None
    ) -> dict:
        """Create a new customer in Paddle.

        Args:
            email: Customer email address
            name: Customer name (optional)
            custom_data: Additional custom data to store with customer

        Returns:
            Customer data from Paddle including customer ID

        Reference: https://developer.paddle.com/api-reference/customers/create-customer
        """
        data = {"email": email}
        if name:
            data["name"] = name
        if custom_data:
            data["custom_data"] = custom_data

        logger.info(
            f"Creating Paddle customer ({self.environment}): {email} (name: {name})"
        )
        response = self._make_request("POST", "/customers", data=data)
        logger.info(
            f"Paddle customer created ({self.environment}): {response.get('data', {}).get('id')}"
        )
        return response.get("data", {})

    def get_customer(self, customer_id: str) -> dict:
        """Get customer details from Paddle.

        Args:
            customer_id: Paddle customer ID

        Returns:
            Customer data from Paddle

        Reference: https://developer.paddle.com/api-reference/customers/get-customer
        """
        logger.info(f"Fetching Paddle customer ({self.environment}): {customer_id}")
        response = self._make_request("GET", f"/customers/{customer_id}")
        return response.get("data", {})

    def update_customer(self, customer_id: str, **kwargs) -> dict:
        """Update customer details in Paddle.

        Args:
            customer_id: Paddle customer ID
            **kwargs: Fields to update (email, name, custom_data, etc.)

        Returns:
            Updated customer data from Paddle

        Reference: https://developer.paddle.com/api-reference/customers/update-customer
        """
        logger.info(f"Updating Paddle customer ({self.environment}): {customer_id}")
        response = self._make_request("PATCH", f"/customers/{customer_id}", data=kwargs)
        return response.get("data", {})

    def get_prices(self, product_id: Optional[str] = None) -> list[dict]:
        """Get pricing information from Paddle.

        Args:
            product_id: Optional product ID to filter prices

        Returns:
            List of price objects

        Reference: https://developer.paddle.com/api-reference/prices/list-prices
        """
        params = {}
        if product_id:
            params["product_id"] = product_id

        logger.info(
            f"Fetching Paddle prices ({self.environment})"
            + (f" for product {product_id}" if product_id else "")
        )
        response = self._make_request("GET", "/prices", params=params)
        return response.get("data", [])

    def create_subscription(
        self, customer_id: str, price_id: str, custom_data: Optional[dict] = None
    ) -> dict:
        """Create a new subscription for a customer.

        Args:
            customer_id: Paddle customer ID
            price_id: Paddle price ID to subscribe to
            custom_data: Additional custom data to store with subscription

        Returns:
            Subscription data from Paddle

        Reference: https://developer.paddle.com/api-reference/subscriptions/create-subscription
        """
        data = {
            "customer_id": customer_id,
            "items": [{"price_id": price_id, "quantity": 1}],
        }
        if custom_data:
            data["custom_data"] = custom_data

        logger.info(
            f"Creating Paddle subscription ({self.environment}): customer={customer_id}, price={price_id}"
        )
        response = self._make_request("POST", "/subscriptions", data=data)
        logger.info(
            f"Paddle subscription created ({self.environment}): {response.get('data', {}).get('id')}"
        )
        return response.get("data", {})

    def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details from Paddle.

        Args:
            subscription_id: Paddle subscription ID

        Returns:
            Subscription data from Paddle

        Reference: https://developer.paddle.com/api-reference/subscriptions/get-subscription
        """
        logger.info(
            f"Fetching Paddle subscription ({self.environment}): {subscription_id}"
        )
        response = self._make_request("GET", f"/subscriptions/{subscription_id}")
        return response.get("data", {})

    def cancel_subscription(
        self, subscription_id: str, effective_from: str = "next_billing_period"
    ) -> dict:
        """Cancel a subscription.

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to cancel ('next_billing_period' or 'immediately')

        Returns:
            Updated subscription data

        Reference: https://developer.paddle.com/api-reference/subscriptions/cancel-subscription
        """
        data = {"effective_from": effective_from}
        logger.info(
            f"Cancelling Paddle subscription ({self.environment}): {subscription_id} (effective: {effective_from})"
        )
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/cancel", data=data
        )
        return response.get("data", {})

    def pause_subscription(
        self, subscription_id: str, effective_from: str = "next_billing_period"
    ) -> dict:
        """Pause a subscription.

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to pause ('next_billing_period' or 'immediately')

        Returns:
            Updated subscription data

        Reference: https://developer.paddle.com/api-reference/subscriptions/pause-subscription
        """
        data = {"effective_from": effective_from}
        logger.info(
            f"Pausing Paddle subscription ({self.environment}): {subscription_id}"
        )
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/pause", data=data
        )
        return response.get("data", {})

    def resume_subscription(self, subscription_id: str) -> dict:
        """Resume a paused subscription.

        Args:
            subscription_id: Paddle subscription ID

        Returns:
            Updated subscription data

        Reference: https://developer.paddle.com/api-reference/subscriptions/resume-subscription
        """
        logger.info(
            f"Resuming Paddle subscription ({self.environment}): {subscription_id}"
        )
        response = self._make_request(
            "POST", f"/subscriptions/{subscription_id}/resume"
        )
        return response.get("data", {})

    def generate_customer_portal_url(
        self, customer_id: str, return_url: Optional[str] = None
    ) -> str:
        """Generate a customer portal session URL for managing subscription.

        The customer portal allows users to:
        - View payment history and invoices
        - Update payment methods
        - View upcoming charges
        - Manage subscription (if enabled)

        Args:
            customer_id: Paddle customer ID
            return_url: Optional URL to return to after portal session

        Returns:
            Customer portal URL

        Reference: https://developer.paddle.com/api-reference/overview
        """
        # For Paddle, we generate a simple customer portal URL
        # The portal is at: https://vendors.paddle.com/subscriptions/customers/{customer_id}
        # For sandbox: https://sandbox-vendors.paddle.com/subscriptions/customers/{customer_id}

        logger.info(
            f"Generating customer portal URL ({self.environment}) for customer: {customer_id}"
        )

        # Paddle's customer portal is accessed directly via URL
        if self.environment == "sandbox":
            portal_url = f"https://sandbox-vendors.paddle.com/subscriptions/customers/{customer_id}"
        else:
            portal_url = f"https://vendors.paddle.com/subscriptions/customers/{customer_id}"

        return portal_url


# Global client instance
# Currently configured to use Paddle as the payment processor
payment_client = PaymentClient()


def get_or_create_payment_customer(user) -> str:
    """Get or create a payment customer for a Django user.

    Args:
        user: Django User instance

    Returns:
        Payment customer ID

    Raises:
        PaymentAPIError: If customer creation fails
    """
    profile = user.profile

    # Check if user already has a payment customer ID
    if profile.payment_customer_id and profile.payment_provider == "paddle":
        logger.info(
            f"User {user.username} already has payment customer ID: {profile.payment_customer_id}"
        )
        return profile.payment_customer_id

    # Create new customer
    custom_data = {
        "user_id": str(user.id),
        "username": user.username,
    }

    customer_data = payment_client.create_customer(
        email=user.email,
        name=user.get_full_name() or user.username,
        custom_data=custom_data,
    )

    # Store customer ID in profile
    profile.payment_provider = "paddle"
    profile.payment_customer_id = customer_data["id"]
    profile.save(
        update_fields=["payment_provider", "payment_customer_id", "updated_at"]
    )

    logger.info(
        f"Created payment customer for user {user.username}: {customer_data['id']}"
    )
    return customer_data["id"]
