"""Billing views for subscription management and payment webhooks."""

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from checktick_app.core.billing import PaymentAPIError, payment_client
from checktick_app.core.email_utils import (
    send_subscription_cancelled_email,
    send_subscription_created_email,
)
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

    # Check if user can downgrade (count active surveys)
    from checktick_app.core.tier_limits import get_tier_limits
    from checktick_app.surveys.models import Survey

    survey_count = Survey.objects.filter(
        owner=user, status__in=["draft", "active"]
    ).count()

    free_tier_limits = get_tier_limits("free")
    can_downgrade = (
        free_tier_limits.max_surveys is None
        or survey_count <= free_tier_limits.max_surveys
    )
    surveys_to_remove = (
        0 if can_downgrade else survey_count - free_tier_limits.max_surveys
    )

    context = {
        "current_tier": profile.account_tier,
        "subscription_status": profile.subscription_status,
        "payment_customer_id": profile.payment_customer_id,
        "payment_subscription_id": profile.payment_subscription_id,
        "payment_environment": settings.PAYMENT_ENVIRONMENT,
        "self_hosted": settings.SELF_HOSTED,  # Hide billing for self-hosters
        "survey_count": survey_count,
        "can_downgrade": can_downgrade,
        "surveys_to_remove": surveys_to_remove,
        "free_tier_limit": free_tier_limits.max_surveys,
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
@ratelimit(key="user", rate="5/h", block=True)
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

        # Check if user will have surveys auto-closed
        from checktick_app.core.tier_limits import get_tier_limits
        from checktick_app.surveys.models import Survey

        survey_count = Survey.objects.filter(
            owner=user, status__in=["draft", "active", "published"]
        ).count()

        free_tier_limits = get_tier_limits("free")

        if free_tier_limits.max_surveys and survey_count > free_tier_limits.max_surveys:
            surveys_to_close = survey_count - free_tier_limits.max_surveys
            messages.success(
                request,
                f"Your subscription has been cancelled. You will retain access to paid features until the end of your billing period. "
                f"At that time, your {surveys_to_close} oldest survey(s) will be automatically closed (read-only). "
                f"You can still view and export data from closed surveys.",
            )
        else:
            messages.success(
                request,
                "Your subscription has been cancelled. You will retain access to paid features until the end of your billing period.",
            )

        logger.info(
            f"User {user.username} cancelled subscription {profile.payment_subscription_id}"
        )

    except PaymentAPIError as e:
        logger.error(f"Error cancelling subscription: {e}")

        # Handle specific Paddle error for pending changes (common in sandbox)
        error_message = str(e)
        if "subscription_locked_pending_changes" in error_message:
            messages.error(
                request,
                "Your subscription has pending changes. Please wait a few moments and try again. "
                "This is common after recently subscribing or updating your plan.",
            )
        else:
            messages.error(
                request,
                "Unable to cancel subscription. Please try again or contact support.",
            )

    return redirect("core:subscription_portal")


@login_required
@require_http_methods(["GET"])
def payment_history(request: HttpRequest) -> HttpResponse:
    """Redirect to Paddle customer portal for payment history and invoices."""
    user = request.user
    profile = user.profile

    if not profile.payment_customer_id or profile.payment_provider != "paddle":
        messages.error(
            request,
            "No payment account found. Payment history is only available for users with active or past subscriptions.",
        )
        return redirect("core:subscription_portal")

    try:
        # Generate customer portal URL with return URL
        return_url = request.build_absolute_uri(reverse("core:subscription_portal"))
        portal_url = payment_client.generate_customer_portal_url(
            profile.payment_customer_id, return_url=return_url
        )

        logger.info(f"User {user.username} accessing payment history via Paddle portal")
        return redirect(portal_url)

    except PaymentAPIError as e:
        logger.error(f"Error generating customer portal URL: {e}")
        messages.error(
            request,
            "Unable to access payment history. Please try again or contact support.",
        )
        return redirect("core:subscription_portal")


@login_required
@require_http_methods(["GET"])
@ratelimit(key="ip", rate="10/m", block=True)
def checkout_success(request: HttpRequest) -> HttpResponse:
    """Handle successful checkout completion.

    This page is shown after user completes payment in Paddle checkout.
    The webhook should have already processed the subscription, so we just
    show a success message and refresh the user's tier info.
    """
    from checktick_app.surveys.models import Team

    tier = request.GET.get("tier", "pro")

    # Refresh user profile to get latest tier info (in case webhook already updated it)
    request.user.profile.refresh_from_db()

    # For team tiers, get the user's team for naming
    user_team = None
    is_team_tier = tier.startswith("team_")
    if is_team_tier:
        user_team = Team.objects.filter(owner=request.user).first()

    context = {
        "tier": tier,
        "current_tier": request.user.profile.account_tier,
        "is_team_tier": is_team_tier,
        "user_team": user_team,
    }

    messages.success(
        request,
        "Payment successful! Your account has been upgraded. It may take a few moments for all features to activate.",
    )

    return render(request, "core/checkout_success.html", context)


@login_required
@require_http_methods(["POST"])
def update_team_name(request: HttpRequest) -> HttpResponse:
    """Update the team name for the user's owned team.

    Called from checkout success page when user names their team.
    """
    from checktick_app.surveys.models import Team

    team_name = request.POST.get("team_name", "").strip()

    if not team_name:
        return JsonResponse({"error": "Team name is required"}, status=400)

    if len(team_name) > 100:
        return JsonResponse({"error": "Team name must be 100 characters or less"}, status=400)

    # Get the user's owned team
    team = Team.objects.filter(owner=request.user).first()

    if not team:
        return JsonResponse({"error": "No team found"}, status=404)

    team.name = team_name
    team.save(update_fields=["name"])

    logger.info(f"Team {team.id} renamed to '{team_name}' by {request.user.username}")

    return JsonResponse({"success": True, "team_name": team_name})


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="100/m", block=True)
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
    if not verify_paddle_webhook_signature(request):
        logger.warning("Invalid Paddle webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=403)

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


def verify_paddle_webhook_signature(request: HttpRequest) -> bool:
    """Verify Paddle webhook signature.

    Paddle signs all webhooks with a signature in the Paddle-Signature header.
    Reference: https://developer.paddle.com/webhooks/signature-verification

    Args:
        request: The HttpRequest object

    Returns:
        bool: True if signature is valid, False otherwise
    """
    import hashlib
    import hmac

    # Get signature from header
    signature = request.headers.get("Paddle-Signature")
    if not signature:
        logger.warning("Missing Paddle-Signature header")
        return False

    # Get webhook secret from settings
    webhook_secret = settings.PAYMENT_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("PAYMENT_WEBHOOK_SECRET not configured")
        # In development, you might want to allow webhooks without signature
        if settings.DEBUG:
            logger.warning(
                "DEBUG mode: Allowing webhook without signature verification"
            )
            return True
        return False

    # Parse signature header: format is "ts=timestamp;h1=signature"
    sig_parts = {}
    for part in signature.split(";"):
        key, value = part.split("=", 1)
        sig_parts[key] = value

    timestamp = sig_parts.get("ts")
    h1_signature = sig_parts.get("h1")

    if not timestamp or not h1_signature:
        logger.warning("Invalid signature format")
        return False

    # Construct the signed payload
    signed_payload = f"{timestamp}:{request.body.decode('utf-8')}"

    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Compare signatures (constant-time comparison to prevent timing attacks)
    if not hmac.compare_digest(h1_signature, expected_signature):
        logger.warning("Signature mismatch")
        return False

    # Optional: Check timestamp to prevent replay attacks
    # Paddle recommends rejecting webhooks older than 5 minutes
    import time

    current_time = int(time.time())
    webhook_time = int(timestamp)
    if abs(current_time - webhook_time) > 300:  # 5 minutes
        logger.warning(f"Webhook timestamp too old: {webhook_time} vs {current_time}")
        return False

    return True


def handle_subscription_created(payload: dict) -> HttpResponse:
    """Handle subscription.created webhook."""
    data = payload.get("data", {})
    subscription_id = data.get("id")
    customer_id = data.get("customer_id")
    status = data.get("status")
    custom_data = data.get("custom_data", {})

    logger.info(f"Processing subscription.created: {subscription_id}")

    # Try to find user by customer ID first
    try:
        profile = UserProfile.objects.get(
            payment_customer_id=customer_id, payment_provider="paddle"
        )
    except UserProfile.DoesNotExist:
        # If not found by customer_id, try to find by user_id in custom_data
        user_id = custom_data.get("userId")
        if user_id:
            try:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                user = User.objects.get(id=user_id)
                profile = user.profile
                # Set the customer_id for future webhooks
                profile.payment_customer_id = customer_id
                profile.payment_provider = "paddle"
            except (User.DoesNotExist, ValueError):
                logger.error(f"No user found for user_id in custom_data: {user_id}")
                return JsonResponse({"error": "User not found"}, status=404)
        else:
            logger.error(
                f"No user found for customer ID: {customer_id} and no userId in custom_data"
            )
            return JsonResponse({"error": "User not found"}, status=404)

    # Update profile
    profile.payment_subscription_id = subscription_id
    profile.subscription_status = status

    # Parse billing period end date
    billing_period = data.get("current_billing_period", {})
    ends_at = billing_period.get("ends_at")
    if ends_at:
        from django.utils.dateparse import parse_datetime

        profile.subscription_current_period_end = parse_datetime(ends_at)

    # Determine tier from price ID
    items = data.get("items", [])
    billing_cycle = "Monthly"  # Default
    if items:
        price_data = items[0].get("price", {})
        price_id = price_data.get("id")

        # Extract billing cycle from price data
        billing_details = price_data.get("billing_cycle", {})
        interval = billing_details.get("interval", "month")
        frequency = billing_details.get("frequency", 1)
        if interval == "year" or frequency == 12:
            billing_cycle = "Yearly"

        # Map price_id to tier
        tier = get_tier_from_price_id(price_id)
        if tier:
            old_tier = profile.account_tier
            profile.account_tier = tier
            profile.tier_changed_at = timezone.now()
            logger.info(
                f"Upgrading user {profile.user.username} from {old_tier} to {tier}"
            )
        else:
            logger.warning(f"Could not determine tier from price_id: {price_id}")
    else:
        logger.warning("No items found in subscription data")

    profile.save()

    # Auto-create team for Team tier users if they don't have one
    # This ensures they become a team admin and see the User Management link
    # Note: Pro tier users are individual accounts with encryption but no collaborators
    team_tiers = [
        UserProfile.AccountTier.TEAM_SMALL,
        UserProfile.AccountTier.TEAM_MEDIUM,
        UserProfile.AccountTier.TEAM_LARGE,
    ]
    if profile.account_tier in team_tiers:
        from checktick_app.surveys.models import Team, TeamMembership

        existing_team = Team.objects.filter(owner=profile.user).first()
        if not existing_team:
            # Determine team size from tier
            size_map = {
                UserProfile.AccountTier.TEAM_SMALL: Team.Size.SMALL,
                UserProfile.AccountTier.TEAM_MEDIUM: Team.Size.MEDIUM,
                UserProfile.AccountTier.TEAM_LARGE: Team.Size.LARGE,
            }
            team_size = size_map.get(profile.account_tier, Team.Size.SMALL)
            team = Team.objects.create(
                name=f"{profile.user.username}'s Team",
                owner=profile.user,
                size=team_size,
            )
            TeamMembership.objects.get_or_create(
                team=team,
                user=profile.user,
                defaults={"role": TeamMembership.Role.ADMIN},
            )
            logger.info(
                f"Auto-created team for {profile.user.username} after subscription upgrade to {profile.account_tier}"
            )

    logger.info(
        f"Subscription created for user {profile.user.username}: {subscription_id} (tier: {profile.account_tier})"
    )

    # Send welcome email
    try:
        send_subscription_created_email(
            profile.user, profile.account_tier, billing_cycle
        )
        logger.info(f"Welcome email sent to {profile.user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {profile.user.email}: {e}")

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

    # Store info for email before downgrade
    old_tier = profile.account_tier

    # Get current billing period end date for the email
    billing_period = data.get("current_billing_period", {})
    ends_at = billing_period.get("ends_at")
    access_until = None
    if ends_at:
        from django.utils.dateparse import parse_datetime

        access_until = parse_datetime(ends_at)

    # Count surveys before downgrade
    from checktick_app.surveys.models import Survey

    survey_count = (
        Survey.objects.filter(owner=profile.user)
        .exclude(status=Survey.Status.CLOSED)
        .count()
    )

    # Calculate how many surveys will be auto-closed
    free_tier_limit = 3
    surveys_to_close = max(0, survey_count - free_tier_limit)

    # Downgrade to FREE tier, auto-closing excess surveys
    success, message = profile.force_downgrade_tier(UserProfile.AccountTier.FREE)

    if not success:
        logger.error(f"Failed to downgrade user {profile.user.username}: {message}")
    else:
        logger.info(f"User {profile.user.username} downgraded to FREE: {message}")

    profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    profile.payment_subscription_id = ""
    profile.save()

    logger.info(
        f"Subscription canceled for user {profile.user.username}: downgrade_success={success}"
    )

    # Send cancellation email
    try:
        send_subscription_cancelled_email(
            profile.user,
            old_tier,
            access_until,
            survey_count,
            surveys_to_close,
            free_tier_limit,
        )
        logger.info(f"Cancellation email sent to {profile.user.email}")
    except Exception as e:
        logger.error(f"Failed to send cancellation email to {profile.user.email}: {e}")

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

    This mapping uses the configured price IDs from settings.PAYMENT_PRICE_IDS.

    Args:
        price_id: Payment processor price ID (pri_*)

    Returns:
        Account tier string (free, pro, team_small, team_large, organization, enterprise)
    """
    # Build reverse mapping from settings
    price_ids = settings.PAYMENT_PRICE_IDS

    # Map each price ID to its tier
    price_to_tier = {}
    for tier, tier_price_id in price_ids.items():
        if tier_price_id:  # Skip empty price IDs
            price_to_tier[tier_price_id] = tier

    tier = price_to_tier.get(price_id)

    if not tier:
        logger.warning(
            f"Unknown price ID: {price_id}. Configured price IDs: {price_ids}"
        )
        return ""

    logger.info(f"Mapped price ID {price_id} to tier {tier}")
    return tier
