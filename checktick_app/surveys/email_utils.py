"""Email utilities for surveys app.

Handles organisation-specific email sending for checkout invitations
and other organisation-related communications.
"""

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.urls import reverse

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

    # Build email context
    _ = {
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

    # Plain text email body
    plain_body = f"""Hi,

You've been invited to complete the subscription setup for {organisation.name}.

Subscription Details:
- {pricing_description}
- Subtotal: £{monthly_cost_ex_vat:.2f}/month
- VAT ({vat_percent}%): £{vat_amount:.2f}
- Total: £{monthly_cost_inc_vat:.2f}/month

To complete your subscription, please click the link below to set up your Direct Debit:

{checkout_url}

This link will expire in 30 days.

If you have any questions, please reply to this email.

Best regards,
The {brand_title} Team
"""

    # HTML email body
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px 8px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Complete Your Subscription</h1>
    </div>

    <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
        <p style="margin-top: 0;">Hi,</p>

        <p>You've been invited to complete the subscription setup for <strong>{organisation.name}</strong>.</p>

        <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #374151;">Subscription Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">{pricing_description}</td>
                    <td style="padding: 8px 0; text-align: right;"></td>
                </tr>
                <tr style="border-top: 1px solid #e5e7eb;">
                    <td style="padding: 8px 0;">Subtotal</td>
                    <td style="padding: 8px 0; text-align: right; font-family: monospace;">£{monthly_cost_ex_vat:.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #6b7280;">VAT ({vat_percent}%)</td>
                    <td style="padding: 8px 0; text-align: right; font-family: monospace; color: #6b7280;">£{vat_amount:.2f}</td>
                </tr>
                <tr style="border-top: 2px solid #e5e7eb; font-weight: bold;">
                    <td style="padding: 12px 0;">Total per month</td>
                    <td style="padding: 12px 0; text-align: right; font-family: monospace; color: #667eea; font-size: 18px;">£{monthly_cost_inc_vat:.2f}</td>
                </tr>
            </table>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{checkout_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">
                Set Up Direct Debit
            </a>
        </div>

        <p style="color: #6b7280; font-size: 14px;">
            This link will expire in 30 days. Payments are protected by the Direct Debit Guarantee.
        </p>

        <p style="color: #6b7280; font-size: 14px;">
            If you have any questions, please reply to this email.
        </p>

        <p style="margin-bottom: 0;">
            Best regards,<br>
            The {brand_title} Team
        </p>
    </div>

    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        {company_name}
    </div>
</body>
</html>
"""

    # Send the email using Django's EmailMultiAlternatives
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[organisation.billing_contact_email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send()

    logger.info(
        f"Sent organisation checkout email for organisation_id={organisation.id}"
    )
