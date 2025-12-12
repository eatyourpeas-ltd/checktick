"""Billing views for subscription management and payment webhooks."""

import json
import logging
from functools import wraps

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


def billing_enabled_required(view_func):
    """Decorator that blocks access to billing views when SELF_HOSTED is True.

    Self-hosted instances have all features enabled without billing.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if settings.SELF_HOSTED:
            messages.info(
                request,
                "Billing is not available on self-hosted instances. "
                "All features are already enabled.",
            )
            return redirect("core:home")
        return view_func(request, *args, **kwargs)

    return wrapper


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
    if profile.payment_subscription_id and profile.payment_provider == "gocardless":
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
@billing_enabled_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="5/h", block=True)
def cancel_subscription(request: HttpRequest) -> HttpResponse:
    """Cancel user's subscription.

    Subscription will remain active until the end of the billing period,
    then account will be downgraded to FREE tier.
    """
    user = request.user
    profile = user.profile

    if not profile.payment_subscription_id or profile.payment_provider != "gocardless":
        messages.error(request, "No active subscription found.")
        return redirect("core:subscription_portal")

    try:
        # Cancel subscription (GoCardless cancels immediately but subscription
        # runs until the end of the current interval)
        payment_client.cancel_subscription(profile.payment_subscription_id)

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

        messages.error(
            request,
            "Unable to cancel subscription. Please try again or contact support.",
        )

    return redirect("core:subscription_portal")


@login_required
@billing_enabled_required
@require_http_methods(["GET"])
def payment_history(request: HttpRequest) -> HttpResponse:
    """Show payment history page.

    GoCardless doesn't have a customer portal like Paddle, so we show
    payment history on our own page. Customers can view their mandate
    in their bank's online banking.
    """
    user = request.user
    profile = user.profile

    if not profile.payment_customer_id or profile.payment_provider != "gocardless":
        messages.error(
            request,
            "No payment account found. Payment history is only available for users with active or past subscriptions.",
        )
        return redirect("core:subscription_portal")

    # Fetch payments from GoCardless
    payments = []
    try:
        payments = payment_client.list_payments(profile.payment_customer_id)
    except PaymentAPIError as e:
        logger.error(f"Error fetching payment history: {e}")
        messages.error(request, "Unable to fetch payment history.")

    context = {
        "payments": payments,
        "current_tier": profile.account_tier,
        "subscription_status": profile.subscription_status,
    }

    return render(request, "core/payment_history.html", context)


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
        return JsonResponse(
            {"error": "Team name must be 100 characters or less"}, status=400
        )

    # Get the user's owned team
    team = Team.objects.filter(owner=request.user).first()

    if not team:
        return JsonResponse({"error": "No team found"}, status=404)

    team.name = team_name
    team.save(update_fields=["name"])

    logger.info(f"Team {team.id} renamed to '{team_name}' by {request.user.username}")

    return JsonResponse({"success": True, "team_name": team_name})


# =============================================================================
# GoCardless Checkout Flow
# =============================================================================


@login_required
@billing_enabled_required
@require_http_methods(["POST"])
@ratelimit(key="user", rate="10/h", block=True)
def start_checkout(request: HttpRequest) -> HttpResponse:
    """Start GoCardless checkout by creating a redirect flow.

    Creates a redirect flow and redirects the user to GoCardless
    to set up their Direct Debit mandate.
    """
    from checktick_app.core.billing import get_or_create_redirect_flow

    tier = request.POST.get("tier", "pro")

    # Validate tier
    if tier not in settings.SUBSCRIPTION_TIERS:
        messages.error(request, "Invalid subscription tier selected.")
        return redirect("core:pricing")

    # Generate a unique session token
    import uuid

    session_token = str(uuid.uuid4())

    # Store checkout info in session
    request.session["checkout_session_token"] = session_token
    request.session["checkout_tier"] = tier

    # Build success URL
    success_url = request.build_absolute_uri(reverse("core:checkout_complete"))

    try:
        redirect_url = get_or_create_redirect_flow(
            user=request.user,
            tier=tier,
            success_url=success_url,
            session_token=session_token,
        )

        if not redirect_url:
            messages.error(request, "Failed to create checkout session.")
            return redirect("core:pricing")

        logger.info(f"User {request.user.username} starting checkout for tier: {tier}")
        return redirect(redirect_url)

    except Exception as e:
        logger.error(f"Error creating redirect flow for {request.user.username}: {e}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect("core:pricing")


@login_required
@billing_enabled_required
@require_http_methods(["GET"])
def checkout_complete(request: HttpRequest) -> HttpResponse:
    """Complete GoCardless checkout after user returns from redirect.

    Called when customer returns from GoCardless after authorising Direct Debit.
    Completes the redirect flow and creates the subscription.
    """
    from checktick_app.core.billing import (
        complete_mandate_setup,
        create_subscription_for_user,
    )

    redirect_flow_id = request.GET.get("redirect_flow_id")
    if not redirect_flow_id:
        messages.error(request, "Invalid checkout session.")
        return redirect("core:pricing")

    # Get session data
    session_token = request.session.get("checkout_session_token")
    tier = request.session.get("checkout_tier", "pro")

    if not session_token:
        messages.error(request, "Checkout session expired. Please try again.")
        return redirect("core:pricing")

    try:
        # Complete the redirect flow (creates customer and mandate)
        customer_id, mandate_id = complete_mandate_setup(
            user=request.user,
            redirect_flow_id=redirect_flow_id,
            session_token=session_token,
        )

        # Create the subscription
        subscription_id = create_subscription_for_user(
            user=request.user,
            tier=tier,
            mandate_id=mandate_id,
        )

        # Clear session data
        request.session.pop("checkout_session_token", None)
        request.session.pop("checkout_tier", None)

        logger.info(
            f"Checkout complete for {request.user.username}: "
            f"subscription={subscription_id}, tier={tier}"
        )

        messages.success(request, "Your subscription has been set up successfully!")
        return redirect("core:checkout_success")

    except Exception as e:
        logger.error(f"Error completing checkout for {request.user.username}: {e}")
        messages.error(
            request,
            "An error occurred setting up your subscription. Please contact support.",
        )
        return redirect("core:pricing")


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key="ip", rate="100/m", block=True)
def payment_webhook(request: HttpRequest) -> HttpResponse:
    """Handle GoCardless webhook events.

    GoCardless sends webhooks for:
    - mandates: created, submitted, active, failed, cancelled, expired
    - subscriptions: created, payment_created, cancelled, finished
    - payments: created, submitted, confirmed, paid_out, failed, cancelled

    Reference: https://developer.gocardless.com/api-reference/#appendix-webhooks
    """
    # Verify webhook signature (important for security)
    if not verify_gocardless_webhook_signature(request):
        logger.warning("Invalid GoCardless webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=403)

    try:
        payload = json.loads(request.body)
        events = payload.get("events", [])

        logger.info(f"Received GoCardless webhook with {len(events)} event(s)")

        # GoCardless sends an array of events in each webhook
        for event in events:
            resource_type = event.get("resource_type")
            action = event.get("action")
            event_id = event.get("id")

            logger.info(
                f"Processing GoCardless event: {resource_type}.{action} ({event_id})"
            )

            # Route to appropriate handler based on resource_type and action
            if resource_type == "subscriptions":
                if action == "created":
                    handle_gocardless_subscription_created(event)
                elif action == "cancelled":
                    handle_gocardless_subscription_cancelled(event)
                elif action == "finished":
                    handle_gocardless_subscription_finished(event)
                elif action == "payment_created":
                    # A payment was created for this subscription
                    logger.info(f"Subscription payment created: {event_id}")
                else:
                    logger.info(f"Ignoring subscription action: {action}")

            elif resource_type == "payments":
                if action == "confirmed":
                    handle_gocardless_payment_confirmed(event)
                elif action == "failed":
                    handle_gocardless_payment_failed(event)
                elif action == "cancelled":
                    handle_gocardless_payment_cancelled(event)
                elif action in ["created", "submitted", "paid_out"]:
                    # Informational events
                    logger.info(f"Payment {action}: {event_id}")
                else:
                    logger.info(f"Ignoring payment action: {action}")

            elif resource_type == "mandates":
                if action == "active":
                    handle_gocardless_mandate_active(event)
                elif action in ["failed", "cancelled", "expired"]:
                    handle_gocardless_mandate_inactive(event, action)
                elif action in ["created", "submitted"]:
                    logger.info(f"Mandate {action}: {event_id}")
                else:
                    logger.info(f"Ignoring mandate action: {action}")

            else:
                logger.info(f"Ignoring resource type: {resource_type}")

        return JsonResponse({"status": "success"}, status=200)

    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}", exc_info=True)
        return JsonResponse({"error": "Internal error"}, status=500)


def verify_gocardless_webhook_signature(request: HttpRequest) -> bool:
    """Verify GoCardless webhook signature.

    GoCardless signs all webhooks with a signature in the Webhook-Signature header.
    Reference: https://developer.gocardless.com/api-reference/#appendix-webhooks

    Args:
        request: The HttpRequest object

    Returns:
        bool: True if signature is valid, False otherwise
    """
    import hashlib
    import hmac

    # Get signature from header
    signature = request.headers.get("Webhook-Signature")
    if not signature:
        logger.warning("Missing Webhook-Signature header")
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

    # GoCardless signature is a simple HMAC-SHA256 of the request body
    # The signature is hex-encoded
    body = request.body

    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    # Compare signatures (constant-time comparison to prevent timing attacks)
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Signature mismatch")
        return False

    return True


# =============================================================================
# GoCardless Event Handlers
# =============================================================================


def handle_gocardless_subscription_created(event: dict) -> None:
    """Handle GoCardless subscriptions.created event.

    This is called when a new subscription is successfully created.
    The subscription is linked via the mandate, which is linked to the customer.

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    subscription_id = links.get("subscription")
    mandate_id = links.get("mandate")

    logger.info(
        f"GoCardless subscription created: {subscription_id} (mandate: {mandate_id})"
    )

    # Find user by mandate_id (stored when redirect flow completes)
    try:
        profile = UserProfile.objects.get(
            payment_mandate_id=mandate_id, payment_provider="gocardless"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for mandate ID: {mandate_id}")
        return

    # Update profile with subscription ID
    profile.payment_subscription_id = subscription_id
    profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
    profile.save(
        update_fields=[
            "payment_subscription_id",
            "subscription_status",
            "updated_at",
        ]
    )

    logger.info(
        f"Subscription {subscription_id} linked to user {profile.user.username}"
    )

    # Send welcome email
    try:
        # Determine billing cycle from subscription metadata if available
        billing_cycle = "monthly"  # Default, can be enhanced with API lookup
        send_subscription_created_email(
            profile.user, profile.account_tier, billing_cycle
        )
        logger.info(f"Welcome email sent to {profile.user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {profile.user.email}: {e}")


def handle_gocardless_subscription_cancelled(event: dict) -> None:
    """Handle GoCardless subscriptions.cancelled event.

    This is called when a subscription is cancelled (by user or admin).

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    subscription_id = links.get("subscription")

    logger.info(f"GoCardless subscription cancelled: {subscription_id}")

    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="gocardless"
        )
    except UserProfile.DoesNotExist:
        logger.error(f"No user found for subscription ID: {subscription_id}")
        return

    # Store info for email before downgrade
    old_tier = profile.account_tier

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

    # Downgrade to FREE tier
    success, message = profile.force_downgrade_tier(UserProfile.AccountTier.FREE)

    if not success:
        logger.error(f"Failed to downgrade user {profile.user.username}: {message}")
    else:
        logger.info(f"User {profile.user.username} downgraded to FREE: {message}")

    profile.subscription_status = UserProfile.SubscriptionStatus.CANCELED
    profile.payment_subscription_id = ""
    profile.save()

    logger.info(f"Subscription canceled for user {profile.user.username}")

    # Send cancellation email
    try:
        send_subscription_cancelled_email(
            profile.user,
            old_tier,
            None,  # access_until - GoCardless cancels immediately
            survey_count,
            surveys_to_close,
            free_tier_limit,
        )
        logger.info(f"Cancellation email sent to {profile.user.email}")
    except Exception as e:
        logger.error(f"Failed to send cancellation email to {profile.user.email}: {e}")


def handle_gocardless_subscription_finished(event: dict) -> None:
    """Handle GoCardless subscriptions.finished event.

    This is called when a subscription reaches its end date (if set).

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    subscription_id = links.get("subscription")

    logger.info(f"GoCardless subscription finished: {subscription_id}")

    # Treat the same as cancelled
    handle_gocardless_subscription_cancelled(event)


def handle_gocardless_payment_confirmed(event: dict) -> None:
    """Handle GoCardless payments.confirmed event.

    This is called when a payment is confirmed (money has been collected).

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    payment_id = links.get("payment")
    subscription_id = links.get("subscription")

    logger.info(
        f"GoCardless payment confirmed: {payment_id} (subscription: {subscription_id})"
    )

    if not subscription_id:
        logger.info("Payment not linked to subscription, ignoring")
        return

    # Update subscription status to active if it was past due
    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="gocardless"
        )
        if profile.subscription_status == UserProfile.SubscriptionStatus.PAST_DUE:
            profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
            profile.save(update_fields=["subscription_status", "updated_at"])
            logger.info(
                f"Payment confirmed, reactivated subscription for {profile.user.username}"
            )
    except UserProfile.DoesNotExist:
        logger.warning(f"No user found for subscription ID: {subscription_id}")


def handle_gocardless_payment_failed(event: dict) -> None:
    """Handle GoCardless payments.failed event.

    This is called when a payment fails (insufficient funds, etc.).

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    payment_id = links.get("payment")
    subscription_id = links.get("subscription")
    details = event.get("details", {})
    cause = details.get("cause", "unknown")
    description = details.get("description", "")

    logger.info(f"GoCardless payment failed: {payment_id} (cause: {cause})")

    if not subscription_id:
        logger.info("Payment not linked to subscription, ignoring")
        return

    try:
        profile = UserProfile.objects.get(
            payment_subscription_id=subscription_id, payment_provider="gocardless"
        )
        profile.subscription_status = UserProfile.SubscriptionStatus.PAST_DUE
        profile.save(update_fields=["subscription_status", "updated_at"])
        logger.info(f"Payment failed for user {profile.user.username}: {description}")
        # TODO: Send payment failed email notification
    except UserProfile.DoesNotExist:
        logger.warning(f"No user found for subscription ID: {subscription_id}")


def handle_gocardless_payment_cancelled(event: dict) -> None:
    """Handle GoCardless payments.cancelled event.

    This is called when a payment is cancelled before being submitted.

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    payment_id = links.get("payment")
    subscription_id = links.get("subscription")

    logger.info(
        f"GoCardless payment cancelled: {payment_id} (subscription: {subscription_id})"
    )
    # Usually informational - no action needed


def handle_gocardless_mandate_active(event: dict) -> None:
    """Handle GoCardless mandates.active event.

    This is called when a mandate becomes active (customer has authorised).
    The mandate is the authorisation to collect payments from the customer.

    Args:
        event: The GoCardless event object
    """
    links = event.get("links", {})
    mandate_id = links.get("mandate")
    customer_id = links.get("customer")

    logger.info(f"GoCardless mandate active: {mandate_id} (customer: {customer_id})")

    # Update user's mandate status if we have the mandate stored
    try:
        profile = UserProfile.objects.get(
            payment_mandate_id=mandate_id, payment_provider="gocardless"
        )
        logger.info(f"Mandate active for user {profile.user.username}")
        # The subscription creation will be handled separately
    except UserProfile.DoesNotExist:
        logger.info(
            f"No user found for mandate ID: {mandate_id} - may not be stored yet"
        )


def handle_gocardless_mandate_inactive(event: dict, action: str) -> None:
    """Handle GoCardless mandates.failed/cancelled/expired events.

    This is called when a mandate becomes inactive for any reason.

    Args:
        event: The GoCardless event object
        action: The action that caused the mandate to become inactive
    """
    links = event.get("links", {})
    mandate_id = links.get("mandate")
    details = event.get("details", {})
    cause = details.get("cause", "unknown")
    description = details.get("description", "")

    logger.info(f"GoCardless mandate {action}: {mandate_id} (cause: {cause})")

    try:
        profile = UserProfile.objects.get(
            payment_mandate_id=mandate_id, payment_provider="gocardless"
        )
        logger.warning(
            f"Mandate {action} for user {profile.user.username}: {description}"
        )
        # If mandate fails, any associated subscription will also fail
        # The subscription.cancelled webhook will handle the downgrade
    except UserProfile.DoesNotExist:
        logger.info(f"No user found for mandate ID: {mandate_id}")


# =============================================================================
# Legacy Paddle Handlers (to be removed after migration)
# =============================================================================


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
    """DEPRECATED: Map payment processor price ID to CheckTick account tier.

    This function is for legacy Paddle support only.
    GoCardless uses metadata to store tier directly.

    Args:
        price_id: Payment processor price ID

    Returns:
        Account tier string or empty string if not found
    """
    # For GoCardless, tier is stored in subscription metadata
    # This function is kept for backward compatibility with any existing Paddle subscriptions
    logger.warning(
        f"get_tier_from_price_id called with {price_id} - this is deprecated for GoCardless"
    )
    return ""
