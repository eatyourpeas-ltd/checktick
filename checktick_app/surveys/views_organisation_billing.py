"""Organisation billing views for checkout and subscription management.

This module handles the organisation checkout flow:
1. Admin creates Organisation with pricing in Django admin
2. Admin sends checkout email with setup token
3. Customer clicks link → checkout page shows pricing
4. Customer proceeds to GoCardless to set up Direct Debit
5. Customer returns → subscription created, organisation activated

Security:
- Token-based access (no login required for checkout)
- Token expiry (30 days default)
- Session validation prevents replay attacks
- Rate limiting on all endpoints
- SELF_HOSTED mode disables billing views
"""

from decimal import Decimal
from functools import wraps
import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from checktick_app.core.billing import PaymentAPIError, payment_client
from checktick_app.surveys.models import Organization

logger = logging.getLogger(__name__)


def billing_enabled_required(view_func):
    """Decorator that blocks access to billing views when SELF_HOSTED is True.

    Self-hosted instances don't need billing - all features are enabled.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if getattr(settings, "SELF_HOSTED", False):
            messages.info(
                request,
                "Billing is not available on self-hosted instances. "
                "All features are already enabled.",
            )
            return redirect("core:home")
        return view_func(request, *args, **kwargs)

    return wrapper


def get_valid_organisation_or_error(request: HttpRequest, token: str):
    """Get an organisation by token with validation checks.

    Returns:
        Tuple of (organisation, error_response) where error_response is None if valid,
        or an HttpResponse to return if invalid.
    """
    # Get organisation by token (404 if not found or inactive)
    try:
        organisation = Organization.objects.get(
            setup_token=token,
            is_active=True,
        )
    except Organization.DoesNotExist:
        messages.error(
            request,
            "Invalid or expired invitation link. Please contact us for assistance.",
        )
        return None, redirect("core:home")

    # Check if setup already completed
    if organisation.setup_completed_at:
        messages.info(
            request,
            "This organisation has already been set up. Please log in to access your account.",
        )
        return None, redirect("login")

    # Check if token has expired
    if organisation.is_setup_expired:
        messages.error(
            request,
            "This invitation link has expired. Please contact us for a new link.",
        )
        return None, redirect("core:home")

    return organisation, None


@require_http_methods(["GET"])
@billing_enabled_required
@ratelimit(key="ip", rate="30/m", block=True)
def organisation_checkout(request: HttpRequest, token: str) -> HttpResponse:
    """Display the organisation checkout page.

    Shows pricing details and allows customer to proceed to GoCardless
    to set up their Direct Debit mandate.

    Args:
        token: The organisation setup token from the invitation email

    Access Control:
        - Valid setup token required
        - Organisation must be active
        - Setup must not be completed
        - Token must not be expired
        - Disabled on SELF_HOSTED instances
    """
    organisation, error_response = get_valid_organisation_or_error(request, token)
    if error_response:
        return error_response

    # Calculate pricing
    vat_rate = Decimal(str(getattr(settings, "VAT_RATE", "0.20")))

    if organisation.billing_type == Organization.BillingType.PER_SEAT:
        seats = organisation.max_seats or 1
        price_per_seat = organisation.price_per_seat or Decimal("0")
        monthly_cost_ex_vat = price_per_seat * seats
    elif organisation.billing_type == Organization.BillingType.FLAT_RATE:
        monthly_cost_ex_vat = organisation.flat_rate_price or Decimal("0")
        seats = organisation.max_seats
        price_per_seat = None
    else:
        monthly_cost_ex_vat = Decimal("0")
        seats = organisation.max_seats
        price_per_seat = None

    vat_amount = monthly_cost_ex_vat * vat_rate
    monthly_cost_inc_vat = monthly_cost_ex_vat + vat_amount

    # Get company details for footer
    company_name = getattr(settings, "COMPANY_NAME", "")
    vat_number = getattr(settings, "VAT_NUMBER", "")

    context = {
        "organisation": organisation,
        "billing_type": organisation.billing_type,
        "price_per_seat": price_per_seat,
        "seats": seats,
        "monthly_cost_ex_vat": monthly_cost_ex_vat,
        "vat_rate_percent": int(vat_rate * 100),
        "vat_amount": vat_amount,
        "monthly_cost_inc_vat": monthly_cost_inc_vat,
        "company_name": company_name,
        "vat_number": vat_number,
        "token": token,
    }

    return render(request, "surveys/organisation_checkout.html", context)


@require_http_methods(["POST"])
@billing_enabled_required
@ratelimit(key="ip", rate="10/h", block=True)
def organisation_start_checkout(request: HttpRequest, token: str) -> HttpResponse:
    """Start GoCardless checkout for an organisation.

    Creates a redirect flow and redirects the customer to GoCardless
    to set up their Direct Debit mandate.

    Args:
        token: The organisation setup token

    Access Control:
        - Valid setup token required
        - Organisation must be active
        - Setup must not be completed
        - Token must not be expired
        - Disabled on SELF_HOSTED instances
    """
    organisation, error_response = get_valid_organisation_or_error(request, token)
    if error_response:
        return error_response

    # Get email from form (optional - pre-filled from billing_contact_email)
    email = request.POST.get("email", "").strip()
    if not email:
        email = organisation.billing_contact_email

    # Generate a unique session token for this checkout
    session_token = str(uuid.uuid4())

    # Store in session for verification when customer returns
    request.session["org_checkout_session_token"] = session_token
    request.session["org_checkout_org_id"] = organisation.id

    # Build success URL
    success_url = request.build_absolute_uri(
        reverse("surveys:organisation_checkout_complete", kwargs={"token": token})
    )

    try:
        # Create GoCardless redirect flow
        redirect_flow = payment_client.create_redirect_flow(
            description=f"Set up Direct Debit for {organisation.name}",
            session_token=session_token,
            success_redirect_url=success_url,
            user_email=email,
            user_name=None,
        )

        redirect_url = redirect_flow.get("redirect_url")
        redirect_flow_id = redirect_flow.get("id")

        # Store redirect flow ID on organisation
        organisation.redirect_flow_id = redirect_flow_id
        organisation.save(update_fields=["redirect_flow_id", "updated_at"])

        logger.info(
            f"Organisation {organisation.id} starting checkout: "
            f"redirect_flow={redirect_flow_id}"
        )

        return redirect(redirect_url)

    except PaymentAPIError as e:
        logger.error(
            f"Error creating redirect flow for organisation {organisation.id}: {e}"
        )
        messages.error(
            request,
            "Unable to connect to payment provider. Please try again.",
        )
        return redirect(
            reverse("surveys:organisation_checkout", kwargs={"token": token})
        )


@billing_enabled_required
@require_http_methods(["GET"])
@ratelimit(key="ip", rate="10/h", block=True)
def organisation_checkout_complete(request: HttpRequest, token: str) -> HttpResponse:
    """Complete organisation checkout after customer returns from GoCardless.

    Completes the redirect flow, creates the subscription, and activates
    the organisation.

    Security:
        - Token must be valid and organisation active
        - Session must match (prevents CSRF)
        - Rate limited to 10 requests/hour
        - Disabled on SELF_HOSTED instances

    Args:
        token: The organisation setup token
    """
    # Get organisation (only check token and active - setup may be completing)
    organisation = get_object_or_404(
        Organization,
        setup_token=token,
        is_active=True,
    )

    # Already completed - redirect to login
    if organisation.setup_completed_at:
        messages.info(request, "This organisation has already been set up.")
        return redirect("login")

    redirect_flow_id = request.GET.get("redirect_flow_id")
    if not redirect_flow_id:
        messages.error(request, "Invalid checkout session.")
        return redirect(
            reverse("surveys:organisation_checkout", kwargs={"token": token})
        )

    # Verify session
    session_token = request.session.get("org_checkout_session_token")
    session_org_id = request.session.get("org_checkout_org_id")

    if not session_token or session_org_id != organisation.id:
        messages.error(request, "Checkout session expired. Please try again.")
        return redirect(
            reverse("surveys:organisation_checkout", kwargs={"token": token})
        )

    try:
        # Complete the redirect flow (creates customer and mandate)
        redirect_flow = payment_client.complete_redirect_flow(
            redirect_flow_id, session_token
        )

        links = redirect_flow.get("links", {})
        customer_id = links.get("customer", "")
        mandate_id = links.get("mandate", "")

        # Calculate subscription amount (in pence)
        vat_rate = Decimal(str(getattr(settings, "VAT_RATE", "0.20")))

        if organisation.billing_type == Organization.BillingType.PER_SEAT:
            seats = organisation.max_seats or 1
            price_per_seat = organisation.price_per_seat or Decimal("0")
            monthly_cost_ex_vat = price_per_seat * seats
        elif organisation.billing_type == Organization.BillingType.FLAT_RATE:
            monthly_cost_ex_vat = organisation.flat_rate_price or Decimal("0")
        else:
            monthly_cost_ex_vat = Decimal("0")

        monthly_cost_inc_vat = monthly_cost_ex_vat * (1 + vat_rate)
        amount_pence = int(monthly_cost_inc_vat * 100)

        # Create subscription
        subscription = payment_client.create_subscription(
            mandate_id=mandate_id,
            amount=amount_pence,
            currency="GBP",
            interval_unit="monthly",
            interval=1,
            name=f"{organisation.name} - Monthly Subscription",
            metadata={
                "organisation_id": str(organisation.id),
                "organisation_name": organisation.name,
                "billing_type": organisation.billing_type,
            },
        )

        subscription_id = subscription.get("id", "")

        # Update organisation with payment details
        organisation.payment_customer_id = customer_id
        organisation.payment_subscription_id = subscription_id
        organisation.save(
            update_fields=[
                "payment_customer_id",
                "payment_subscription_id",
                "updated_at",
            ]
        )

        # Complete setup (marks as active, clears token)
        organisation.complete_setup()

        # Clear session data
        request.session.pop("org_checkout_session_token", None)
        request.session.pop("org_checkout_org_id", None)

        logger.info(
            f"Organisation {organisation.id} checkout complete: "
            f"customer={customer_id}, subscription={subscription_id}"
        )

        messages.success(
            request,
            f"Welcome to {organisation.name}! Your subscription has been set up successfully. "
            f"Please log in to get started.",
        )

        # Redirect to login (owner can now claim the organisation)
        return redirect("login")

    except PaymentAPIError as e:
        logger.error(
            f"Error completing checkout for organisation {organisation.id}: {e}"
        )
        messages.error(
            request,
            "An error occurred setting up your subscription. Please contact support.",
        )
        return redirect(
            reverse("surveys:organisation_checkout", kwargs={"token": token})
        )
