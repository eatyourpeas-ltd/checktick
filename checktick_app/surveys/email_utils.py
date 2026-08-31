"""Email utilities for surveys app.

Handles organisation-specific email sending for checkout invitations
and other organisation-related communications.
"""

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

from checktick_app.core.email_utils import get_platform_branding, send_branded_email

if TYPE_CHECKING:
    from checktick_app.surveys.models import Organization

logger = logging.getLogger(__name__)


def send_organisation_checkout_email(
    organisation: "Organization",
    request: HttpRequest | None = None,
) -> None:
    """Send a checkout invitation email to an organisation.

    Sends an email to the billing contact with a link to complete
    the Direct Debit setup.

    Args:
        organisation: The Organisation instance to send the email for
        request: Optional HttpRequest for building absolute URLs

    Raises:
        ValueError: If organisation has no billing email or setup token
        Exception: If email sending fails
    """
    if not organisation.billing_contact_email:
        raise ValueError("Organisation has no billing contact email")

    if not organisation.setup_token:
        raise ValueError("Organisation has no setup token")

    # Build checkout URL
    checkout_path = reverse(
        "surveys:organisation_checkout",
        kwargs={"token": organisation.setup_token},
    )

    if request:
        checkout_url = request.build_absolute_uri(checkout_path)
    else:
        site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
        checkout_url = f"{site_url.rstrip('/')}{checkout_path}"

    # Calculate pricing for email
    from decimal import Decimal

    vat_rate = Decimal(str(getattr(settings, "VAT_RATE", "0.20")))
    vat_percent = int(vat_rate * 100)

    if organisation.billing_type == "per_seat":
        seats = organisation.max_seats or 1
        price_per_seat = organisation.price_per_seat or Decimal("0")
        monthly_cost_ex_vat = price_per_seat * seats
        pricing_description = f"£{price_per_seat:.2f}/seat × {seats} seats"
    elif organisation.billing_type == "flat_rate":
        monthly_cost_ex_vat = organisation.flat_rate_price or Decimal("0")
        pricing_description = "Flat rate subscription"
    else:
        monthly_cost_ex_vat = Decimal("0")
        pricing_description = ""

    vat_amount = monthly_cost_ex_vat * vat_rate
    monthly_cost_inc_vat = monthly_cost_ex_vat + vat_amount

    # Get company info
    company_name = getattr(settings, "COMPANY_NAME", "CheckTick")
    brand_title = getattr(settings, "BRAND_TITLE", "CheckTick")

    # Email content
    subject = f"Complete your {organisation.name} subscription"

    context = {
        "organisation_name": organisation.name,
        "checkout_url": checkout_url,
        "pricing_description": pricing_description,
        "monthly_cost_ex_vat": f"£{monthly_cost_ex_vat:.2f}",
        "vat_percent": vat_percent,
        "vat_amount": f"£{vat_amount:.2f}",
        "monthly_cost_inc_vat": f"£{monthly_cost_inc_vat:.2f}",
        "company_name": company_name,
        "brand_title": brand_title,
        "expires_days": 30,  # Token expiry
    }

    markdown_content = render_to_string("emails/organisation_checkout.md", context)

    sent = send_branded_email(
        to_email=organisation.billing_contact_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=get_platform_branding(),
        context=context,
    )
    if not sent:
        raise RuntimeError("Failed to send organisation checkout email")

    logger.info(
        f"Sent organisation checkout email for organisation_id={organisation.id}"
    )
