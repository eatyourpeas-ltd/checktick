"""Billing views for subscription management and payment webhooks."""

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from checktick_app.core.billing import PaymentAPIError, payment_client
from checktick_app.core.models import UserProfile

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def subscription_portal(request: HttpRequest) -> HttpResponse:
    """Subscription management portal.

    Shows current subscription status and provides links to:
    - Upgrade/downgrade tier
    - Manage payment method
    - View billing history
    - Cancel subscription
    """
    user = request.user
    profile = user.profile

    context = {
        "current_tier": profile.account_tier,
        "subscription_status": profile.subscription_status,
        "payment_customer_id": profile.payment_customer_id,
        "payment_subscription_id": profile.payment_subscription_id,
        "payment_environment": settings.PAYMENT_ENVIRONMENT,
        "self_hosted": settings.SELF_HOSTED,  # Hide billing for self-hosters
    }

    # If user has a subscription, fetch current details from payment processor
    if profile.payment_subscription_id and profile.payment_provider == "paddle":
        try:
            subscription_data = payment_client.get_subscription(
                profile.payment_subscription_id
            )
            context["subscription_data"] = subscription_data
        except PaymentAPIError as e:
            logger.error(f"Error fetching subscription: {e}")
            messages.error(request, "Unable to fetch subscription details.")

    return render(request, "core/subscription_portal.html", context)


@login_required
@require_http_methods(["POST"])
def cancel_subscription(request: HttpRequest) -> HttpResponse:
    """Cancel user's subscription.

    Subscription will remain active until the end of the billing period,
    then account will be downgraded to FREE tier.
    """
    user = request.user
    profile = user.profile

    if not profile.payment_subscription_id or profile.payment_provider != "paddle":
        messages.error(request, "No active subscription found.")
        return redirect("core:subscription_portal")

    try:
        # Cancel at end of billing period
        payment_client.cancel_subscription(
            profile.payment_subscription_id, effective_from="next_billing_period"
        )

        # Update status
        profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
        profile.save(update_fields=["subscription_status", "updated_at"])

        messages.success(
            request,
            "Your subscription has been cancelled. You will retain access to paid features until the end of your billing period.",
        )
        logger.info(
            f"User {user.username} cancelled subscription {profile.payment_subscription_id}"
        )

    except PaymentAPIError as e:
        logger.error(f"Error cancelling subscription: {e}")
        messages.error(
            request,
            "Unable to cancel subscription. Please try again or contact support.",
        )

    return redirect("core:subscription_portal")


@login_required
@require_http_methods(["GET"])
def checkout_success(request: HttpRequest) -> HttpResponse:
    """Handle successful checkout completion.

    This page is shown after user completes payment in Paddle checkout.
    The webhook should have already processed the subscription, so we just
    show a success message and refresh the user's tier info.
    """
    tier = request.GET.get("tier", "pro")

    # Refresh user profile to get latest tier info (in case webhook already updated it)
    request.user.profile.refresh_from_db()

    context = {
        "tier": tier,
        "current_tier": request.user.profile.account_tier,
    }

    messages.success(
        request,
        "Payment successful! Your account has been upgraded. It may take a few moments for all features to activate.",
    )

    return render(request, "core/checkout_success.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request: HttpRequest) -> HttpResponse:
    """Handle payment processor webhook events.

    Paddle sends webhooks for:
    - subscription.created
    - subscription.updated
    - subscription.canceled
    - subscription.past_due
    - transaction.completed
    - transaction.payment_failed

    Reference: https://developer.paddle.com/webhooks/overview
    """
    # Verify webhook signature (important for security)
    # Note: Paddle webhook signature verification should be implemented here
    # For now, we'll process the webhook but log a warning

    try:
        payload = json.loads(request.body)
        event_type = payload.get("event_type")

        logger.info(f"Received payment webhook: {event_type}")

        # Route to appropriate handler
        if event_type == "subscription.created":
            return handle_subscription_created(payload)
        elif event_type == "subscription.updated":
            return handle_subscription_updated(payload)
        elif event_type == "subscription.canceled":
            return handle_subscription_canceled(payload)
        elif event_type == "subscription.past_due":
            return handle_subscription_past_due(payload)
        elif event_type == "transaction.completed":
            return handle_transaction_completed(payload)
        elif event_type == "transaction.payment_failed":
            return handle_transaction_failed(payload)
        else:
            logger.warning(f"Unhandled webhook event type: {event_type}")
            return JsonResponse({"status": "ignored"}, status=200)

    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}", exc_info=True)
        return JsonResponse({"error": "Internal error"}, status=500)


def handle_subscription_created(payload: dict) -> HttpResponse:
    """Handle subscription.created webhook."""
    data = payload.get("data", {})
    subscription_id = data.get("id")
    customer_id = data.get("customer_id")
    status = data.get("status")
    # custom_data = data.get("custom_data", {})

    logger.info(f"Processing subscription.created: {subscription_id}")

    # Find user by customer ID
    try:
        profile = UserProfile.objects.get(
            payment_customer_id=customer_id, payment_provider="paddle"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for customer ID: {customer_id}")
        return JsonResponse({"error": "User not found"}, status=404)

    # Update profile
    profile.payment_subscription_id = subscription_id
    profile.subscription_status = status
    profile.subscription_current_period_end = data.get(
        "current_billing_period", {}
    ).get("ends_at")

    # Determine tier from price ID or custom data
    # This should be mapped based on your Paddle product configuration
    items = data.get("items", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        # Map price_id to tier (you'll need to configure this)
        tier_mapping = get_tier_from_price_id(price_id)
        if tier_mapping:
            profile.account_tier = tier_mapping

    profile.tier_changed_at = timezone.now()
    profile.save()

    logger.info(
        f"Subscription created for user {profile.user.username}: {subscription_id} (tier: {profile.account_tier})"
    )

    return JsonResponse({"status": "success"}, status=200)


def handle_subscription_updated(payload: dict) -> HttpResponse:
    """Handle subscription.updated webhook."""
    data = payload.get("data", {})
    subscription_id = data.get("id")
    status = data.get("status")

    logger.info(f"Processing subscription.updated: {subscription_id}")

    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="paddle"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for subscription ID: {subscription_id}")
        return JsonResponse({"error": "Subscription not found"}, status=404)

    # Update status
    profile.subscription_status = status
    profile.subscription_current_period_end = data.get(
        "current_billing_period", {}
    ).get("ends_at")
    profile.save(
        update_fields=[
            "subscription_status",
            "subscription_current_period_end",
            "updated_at",
        ]
    )

    logger.info(
        f"Subscription updated for user {profile.user.username}: status={status}"
    )

    return JsonResponse({"status": "success"}, status=200)


def handle_subscription_canceled(payload: dict) -> HttpResponse:
    """Handle subscription.canceled webhook."""
    data = payload.get("data", {})
    subscription_id = data.get("id")

    logger.info(f"Processing subscription.canceled: {subscription_id}")

    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="paddle"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for subscription ID: {subscription_id}")
        return JsonResponse({"error": "Subscription not found"}, status=404)

    # Downgrade to FREE tier
    success, message = profile.downgrade_tier(UserProfile.AccountTier.FREE)

    if not success:
        # User has too many surveys - log warning but update subscription status
        logger.warning(
            f"User {profile.user.username} subscription canceled but cannot downgrade: {message}"
        )

    profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    profile.payment_subscription_id = ""
    profile.save()

    logger.info(
        f"Subscription canceled for user {profile.user.username}: downgrade_success={success}"
    )

    return JsonResponse({"status": "success"}, status=200)


def handle_subscription_past_due(payload: dict) -> HttpResponse:
    """Handle subscription.past_due webhook."""
    data = payload.get("data", {})
    subscription_id = data.get("id")

    logger.info(f"Processing subscription.past_due: {subscription_id}")

    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="paddle"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for subscription ID: {subscription_id}")
        return JsonResponse({"error": "Subscription not found"}, status=404)

    profile.subscription_status = UserProfile.SubscriptionStatus.PAST_DUE
    profile.save(update_fields=["subscription_status", "updated_at"])

    logger.info(f"Subscription past due for user {profile.user.username}")

    # TODO: Send email notification to user

    return JsonResponse({"status": "success"}, status=200)


def handle_transaction_completed(payload: dict) -> HttpResponse:
    """Handle transaction.completed webhook."""
    data = payload.get("data", {})
    transaction_id = data.get("id")
    customer_id = data.get("customer_id")

    logger.info(f"Processing transaction.completed: {transaction_id}")

    # Update subscription status to active if it was past due
    try:
        profile = UserProfile.objects.get(
            payment_customer_id=customer_id, payment_provider="paddle"
        )
        if profile.subscription_status == UserProfile.SubscriptionStatus.PAST_DUE:
            profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
            profile.save(update_fields=["subscription_status", "updated_at"])
            logger.info(
                f"Transaction completed, reactivated subscription for {profile.user.username}"
            )
    except UserProfile.DoesNotExist:
        logger.warning(f"No user found for customer ID in transaction: {customer_id}")

    return JsonResponse({"status": "success"}, status=200)


def handle_transaction_failed(payload: dict) -> HttpResponse:
    """Handle transaction.payment_failed webhook."""
    data = payload.get("data", {})
    transaction_id = data.get("id")
    customer_id = data.get("customer_id")

    logger.info(f"Processing transaction.payment_failed: {transaction_id}")

    # Mark subscription as past due or unpaid
    try:
        profile = UserProfile.objects.get(
            payment_customer_id=customer_id, payment_provider="paddle"
        )
        profile.subscription_status = UserProfile.SubscriptionStatus.PAST_DUE
        profile.save(update_fields=["subscription_status", "updated_at"])
        logger.info(f"Payment failed for user {profile.user.username}")
        # TODO: Send email notification
    except UserProfile.DoesNotExist:
        logger.warning(
            f"No user found for customer ID in failed transaction: {customer_id}"
        )

    return JsonResponse({"status": "success"}, status=200)


def get_tier_from_price_id(price_id: str) -> str:
    """Map payment processor price ID to CheckTick account tier.

    This mapping should be configured based on your payment processor product setup.
    You'll need to create products and prices in your payment processor and map them here.

    Args:
        price_id: Payment processor price ID

    Returns:
        Account tier string
    """
    # TODO: Configure this mapping based on your payment processor products
    # Example mapping (you'll need to replace with actual price IDs):
    PRICE_TIER_MAPPING = {
        # Sandbox price IDs (for testing)
        "pri_01example_pro_monthly": UserProfile.AccountTier.PRO,
        "pri_01example_pro_annual": UserProfile.AccountTier.PRO,
        "pri_01example_org_monthly": UserProfile.AccountTier.ORGANIZATION,
        "pri_01example_org_annual": UserProfile.AccountTier.ORGANIZATION,
        # Production price IDs (add when available)
    }

    tier = PRICE_TIER_MAPPING.get(price_id, "")
    if not tier:
        logger.warning(f"Unknown price ID: {price_id}")
    return tier
