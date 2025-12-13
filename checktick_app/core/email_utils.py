"""Email utilities for sending branded, themed emails.

Supports both platform-level branding (for account emails) and survey-level
theming (for survey-specific emails).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import markdown

logger = logging.getLogger(__name__)


def get_platform_branding() -> Dict[str, Any]:
    """Get platform-level branding configuration.

    Returns brand settings from settings.py or SiteBranding model.
    Used for account-related emails (welcome, password change, etc.)
    """
    from checktick_app.core.models import SiteBranding

    # Default primary color from settings or fallback
    default_primary = getattr(settings, "BRAND_PRIMARY_COLOR", "#3b82f6")

    # Try to get from database first
    try:
        branding = SiteBranding.objects.first()
        if branding:
            return {
                "title": getattr(settings, "BRAND_TITLE", "CheckTick"),
                "theme_name": branding.default_theme,
                "icon_url": branding.icon_url
                or getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
                "font_heading": branding.font_heading
                or getattr(
                    settings,
                    "BRAND_FONT_HEADING",
                    "'IBM Plex Sans', sans-serif",
                ),
                "font_body": branding.font_body
                or getattr(settings, "BRAND_FONT_BODY", "Merriweather, serif"),
                "primary_color": default_primary,
            }
    except Exception:
        pass

    # Fall back to settings
    return {
        "title": getattr(settings, "BRAND_TITLE", "CheckTick"),
        "theme_name": getattr(settings, "BRAND_THEME", "checktick-light"),
        "icon_url": getattr(settings, "BRAND_ICON_URL", "/static/favicon.ico"),
        "font_heading": getattr(
            settings, "BRAND_FONT_HEADING", "'IBM Plex Sans', sans-serif"
        ),
        "font_body": getattr(settings, "BRAND_FONT_BODY", "Merriweather, serif"),
        "primary_color": default_primary,
    }


def get_survey_branding(survey) -> Dict[str, Any]:
    """Get survey-level branding configuration.

    Returns survey-specific theme overrides for survey-related emails.
    Falls back to platform branding if no survey overrides exist.
    """
    platform_brand = get_platform_branding()

    if not survey:
        return platform_brand

    style = survey.style or {}

    return {
        "title": style.get("title") or survey.name or platform_brand["title"],
        "theme_name": style.get("theme_name") or platform_brand["theme_name"],
        "icon_url": style.get("icon_url") or platform_brand["icon_url"],
        "font_heading": style.get("font_heading") or platform_brand["font_heading"],
        "font_body": style.get("font_body") or platform_brand["font_body"],
        "primary_color": style.get("primary_color") or platform_brand["primary_color"],
        "survey_name": survey.name,
        "survey_slug": survey.slug,
    }


def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown text to HTML.

    Supports standard markdown features including:
    - Headers
    - Bold, italic
    - Lists
    - Links
    - Code blocks
    """
    return markdown.markdown(
        markdown_text,
        extensions=["extra", "nl2br", "sane_lists"],
    )


def send_branded_email(
    to_email: str,
    subject: str,
    markdown_content: str,
    branding: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Send a branded email with markdown content.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        markdown_content: Email body in markdown format
        branding: Brand configuration (platform or survey-level)
        context: Additional template context variables
        from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)

    Returns:
        True if email sent successfully, False otherwise
    """
    if not branding:
        branding = get_platform_branding()

    if not context:
        context = {}

    # Convert markdown to HTML
    html_content = markdown_to_html(markdown_content)

    # Build full context for template
    email_context = {
        "subject": subject,
        "content": html_content,
        "brand": branding,
        "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        **context,
    }

    # Render HTML email with branding
    try:
        html_message = render_to_string(
            "emails/base_email.html",
            email_context,
        )
    except Exception as e:
        logger.error(
            f"Failed to render email template: {e}",
            exc_info=True,
            extra={
                "recipient": to_email,
                "subject": subject,
                "template": "emails/base_email.html",
            },
        )
        # Fallback to simple HTML
        html_message = f"""
        <html>
            <body style="font-family: {branding.get('font_body', 'sans-serif')};">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: {branding.get('primary_color', '#3b82f6')};">
                        {branding.get('title', 'CheckTick')}
                    </h1>
                    {html_content}
                </div>
            </body>
        </html>
        """

    # Generate plain text version
    plain_message = strip_tags(html_content)

    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send email to {to_email}: {subject}",
            exc_info=True,
            extra={
                "recipient": to_email,
                "subject": subject,
                "error_type": type(e).__name__,
                "from_email": from_email or settings.DEFAULT_FROM_EMAIL,
                "email_backend": settings.EMAIL_BACKEND,
            },
        )
        return False


def send_welcome_email(user) -> bool:
    """Send welcome email to newly registered user.

    Uses platform-level branding.
    """
    from checktick_app.core.models import UserEmailPreferences

    logger.info(
        f"Attempting to send welcome email to {user.email} (username: {user.username})"
    )

    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_welcome_email:
        logger.info(
            f"Welcome email skipped for {user.username} (user preference disabled)"
        )
        return False

    branding = get_platform_branding()

    subject = f"Welcome to {branding['title']}!"

    markdown_content = render_to_string(
        "emails/welcome.md",
        {
            "user": user,
            "brand_title": branding["title"],
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={"user": user},
    )


def send_password_change_email(user) -> bool:
    """Send security notification when password is changed.

    Uses platform-level branding.
    Note: This is a security feature and respects user preferences.
    """
    from checktick_app.core.models import UserEmailPreferences

    logger.info(
        f"Attempting to send password change email to {user.email} (username: {user.username})"
    )

    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_password_change_email:
        logger.info(
            f"Password change email skipped for {user.username} (user preference disabled)"
        )
        return False

    branding = get_platform_branding()

    subject = "Password Changed - Security Notification"

    markdown_content = render_to_string(
        "emails/password_changed.md",
        {
            "user": user,
            "brand_title": branding["title"],
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={"user": user},
    )


def send_security_email(
    user,
    subject: str,
    template_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """Send a security notification email.

    Security emails are always sent regardless of user preferences,
    as they inform users of important security events.

    Args:
        user: The user to send the email to
        subject: Email subject line
        template_name: Path to the email template (.md file)
        context: Additional context for the template

    Returns:
        True if email sent successfully, False otherwise
    """
    if not user.email:
        logger.warning(f"Cannot send security email - user {user.id} has no email")
        return False

    branding = get_platform_branding()

    # Build template context
    template_context = {
        "user": user,
        "brand_title": branding["title"],
        "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
    }
    if context:
        template_context.update(context)

    # Render markdown content
    try:
        markdown_content = render_to_string(template_name, template_context)
    except TemplateDoesNotExist:
        logger.error(f"Security email template not found: {template_name}")
        return False

    return send_branded_email(
        to_email=user.email,
        subject=f"🔒 {subject}",
        markdown_content=markdown_content,
        branding=branding,
        context=template_context,
    )


def send_survey_created_email(user, survey) -> bool:
    """Send notification when survey is created.

    Uses survey-level branding if configured, otherwise platform branding.
    """
    from checktick_app.core.models import UserEmailPreferences

    logger.info(
        f"Attempting to send survey created email to {user.email} for survey: {survey.name} ({survey.slug})"
    )

    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_survey_created_email:
        logger.info(
            f"Survey created email skipped for {user.username} (user preference disabled)"
        )
        return False

    branding = get_survey_branding(survey)

    subject = f"Survey Created: {survey.name}"

    markdown_content = render_to_string(
        "emails/survey_created.md",
        {
            "user": user,
            "survey": survey,
            "brand_title": branding["title"],
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={"user": user, "survey": survey},
    )


def send_survey_deleted_email(user, survey_name: str, survey_slug: str) -> bool:
    """Send notification when survey is deleted.

    Note: Survey object is already deleted, so we use name/slug.
    Uses platform branding since survey no longer exists.
    """
    from checktick_app.core.models import UserEmailPreferences

    logger.info(
        f"Attempting to send survey deleted email to {user.email} for survey: {survey_name} ({survey_slug})"
    )

    prefs = UserEmailPreferences.get_or_create_for_user(user)
    if not prefs.send_survey_deleted_email:
        logger.info(
            f"Survey deleted email skipped for {user.username} (user preference disabled)"
        )
        return False

    branding = get_platform_branding()

    subject = f"Survey Deleted: {survey_name}"

    markdown_content = render_to_string(
        "emails/survey_deleted.md",
        {
            "user": user,
            "survey_name": survey_name,
            "survey_slug": survey_slug,
            "brand_title": branding["title"],
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "user": user,
            "survey_name": survey_name,
            "survey_slug": survey_slug,
        },
    )


def send_survey_invite_email(
    to_email: str,
    survey,
    token: str,
    contact_email: Optional[str] = None,
    qr_code_data_uri: Optional[str] = None,
) -> bool:
    """Send survey invitation email with unique token link.

    Args:
        to_email: Recipient email address
        survey: Survey object
        token: Unique access token string
        contact_email: Optional contact email for questions
        qr_code_data_uri: Optional QR code as data URI to include in email

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.conf import settings

    logger.info(
        f"Attempting to send survey invite email to {to_email} for survey: {survey.name} ({survey.slug})"
    )

    branding = get_survey_branding(survey)

    # Build the survey link with token
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    survey_link = f"{site_url}/surveys/{survey.slug}/take/token/{token}/"

    # Get organization name if available
    organization_name = None
    if survey.organization:
        organization_name = survey.organization.name

    # Format end date if available
    end_date = None
    if survey.end_at:
        from django.utils.formats import date_format

        end_date = date_format(survey.end_at, "DATETIME_FORMAT")

    subject = f"You're invited to complete: {survey.name}"

    markdown_content = render_to_string(
        "emails/survey_invite.md",
        {
            "survey_name": survey.name,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "brand_title": branding["title"],
            "qr_code_data_uri": qr_code_data_uri,
        },
    )

    return send_branded_email(
        to_email=to_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "survey_name": survey.name,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "qr_code_data_uri": qr_code_data_uri,
        },
    )


def send_authenticated_survey_invite_existing_user(
    to_email: str,
    survey,
    contact_email: Optional[str] = None,
    qr_code_data_uri: Optional[str] = None,
) -> bool:
    """Send survey invitation to existing authenticated user.

    Args:
        to_email: Recipient email address (existing user)
        survey: Survey object
        contact_email: Optional contact email for questions
        qr_code_data_uri: Optional QR code as data URI to include in email

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.conf import settings

    logger.info(
        f"Attempting to send authenticated survey invite to existing user {to_email} for survey: {survey.name} ({survey.slug})"
    )

    branding = get_survey_branding(survey)

    # Build the survey link (requires login)
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    survey_link = f"{site_url}/surveys/{survey.slug}/take/"

    # Get organization name if available
    organization_name = None
    if survey.organization:
        organization_name = survey.organization.name

    # Format end date if available
    end_date = None
    if survey.end_at:
        from django.utils.formats import date_format

        end_date = date_format(survey.end_at, "DATETIME_FORMAT")

    subject = f"You're invited to complete: {survey.name}"

    markdown_content = render_to_string(
        "emails/survey_invite_authenticated.md",
        {
            "survey_name": survey.name,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "brand_title": branding["title"],
            "qr_code_data_uri": qr_code_data_uri,
        },
    )

    return send_branded_email(
        to_email=to_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "survey_name": survey.name,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "qr_code_data_uri": qr_code_data_uri,
        },
    )


def send_authenticated_survey_invite_new_user(
    to_email: str,
    survey,
    contact_email: Optional[str] = None,
    qr_code_data_uri: Optional[str] = None,
) -> bool:
    """Send survey invitation to new user (needs to create account).

    Args:
        to_email: Recipient email address (no existing account)
        survey: Survey object
        contact_email: Optional contact email for questions
        qr_code_data_uri: Optional QR code as data URI to include in email

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.conf import settings

    logger.info(
        f"Attempting to send authenticated survey invite to new user {to_email} for survey: {survey.name} ({survey.slug})"
    )

    branding = get_survey_branding(survey)

    # Build signup link with redirect to survey
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    signup_link = (
        f"{site_url}/signup/?next=/surveys/{survey.slug}/take/&email={to_email}"
    )
    survey_link = f"{site_url}/surveys/{survey.slug}/take/"

    # Get organization name if available
    organization_name = None
    if survey.organization:
        organization_name = survey.organization.name

    # Format end date if available
    end_date = None
    if survey.end_at:
        from django.utils.formats import date_format

        end_date = date_format(survey.end_at, "DATETIME_FORMAT")

    subject = f"You're invited to join CheckTick and complete: {survey.name}"

    markdown_content = render_to_string(
        "emails/survey_invite_authenticated_new.md",
        {
            "survey_name": survey.name,
            "signup_link": signup_link,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "brand_title": branding["title"],
            "qr_code_data_uri": qr_code_data_uri,
        },
    )

    return send_branded_email(
        to_email=to_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "survey_name": survey.name,
            "signup_link": signup_link,
            "survey_link": survey_link,
            "organization_name": organization_name,
            "end_date": end_date,
            "contact_email": contact_email,
            "qr_code_data_uri": qr_code_data_uri,
        },
    )


def send_subscription_created_email(
    user, tier: str, billing_cycle: str = "Monthly"
) -> bool:
    """Send welcome email with VAT invoice when user subscribes to a paid plan.

    Args:
        user: Django User instance
        tier: Account tier (pro, enterprise)
        billing_cycle: Billing cycle (Monthly, Yearly)

    Returns:
        True if email sent successfully, False otherwise
    """
    from datetime import datetime
    import uuid

    logger.info(
        f"Attempting to send subscription created email (tier: {tier}, cycle: {billing_cycle})"
    )

    branding = get_platform_branding()

    # Get tier pricing info
    tier_config = getattr(settings, "SUBSCRIPTION_TIERS", {}).get(tier, {})
    amount_inc_vat = tier_config.get("amount", 0) / 100  # Convert pence to pounds
    amount_ex_vat = tier_config.get("amount_ex_vat", 0) / 100
    vat_amount = amount_inc_vat - amount_ex_vat
    vat_rate = getattr(settings, "VAT_RATE", 0.20) * 100  # As percentage

    # Invoice details
    invoice_number = (
        f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    )
    invoice_date = datetime.now().strftime("%d %B %Y")
    vat_number = getattr(settings, "VAT_NUMBER", "")
    company_name = getattr(settings, "COMPANY_NAME", branding["title"])
    company_address = getattr(settings, "COMPANY_ADDRESS", "")

    tier_display = tier.title()
    subject = f"Welcome to {branding['title']} {tier_display}!"

    markdown_content = render_to_string(
        "emails/subscription_created.md",
        {
            "user": user,
            "brand_title": branding["title"],
            "tier": tier,
            "tier_name": tier_display,
            "billing_cycle": billing_cycle,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            # VAT invoice details
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "amount_ex_vat": f"£{amount_ex_vat:.2f}",
            "vat_amount": f"£{vat_amount:.2f}",
            "vat_rate": f"{vat_rate:.0f}%",
            "amount_inc_vat": f"£{amount_inc_vat:.2f}",
            "vat_number": vat_number,
            "company_name": company_name,
            "company_address": company_address,
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "user": user,
            "tier": tier,
            "tier_name": tier_display,
            "billing_cycle": billing_cycle,
        },
    )


def send_subscription_cancelled_email(
    user,
    tier: str,
    end_date,
    survey_count: int = 0,
    surveys_to_close: int = 0,
    free_tier_limit: int = 3,
) -> bool:
    """Send notification when user cancels subscription.

    Args:
        user: Django User instance
        tier: Account tier being cancelled
        end_date: Date when subscription access ends
        survey_count: Current number of surveys user owns
        surveys_to_close: Number of surveys that will be auto-closed
        free_tier_limit: Max surveys allowed on free tier

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.utils.formats import date_format

    logger.info(
        f"Attempting to send subscription cancelled email to {user.email} (username: {user.username}, tier: {tier})"
    )

    branding = get_platform_branding()

    tier_display = tier.title()
    subject = f"Subscription Cancelled - {branding['title']}"

    # Format the end date
    access_until_date = (
        date_format(end_date, "F j, Y") if end_date else "your billing period ends"
    )

    markdown_content = render_to_string(
        "emails/subscription_cancelled.md",
        {
            "user": user,
            "brand_title": branding["title"],
            "tier": tier,
            "tier_name": tier_display,
            "access_until_date": access_until_date,
            "survey_count": survey_count,
            "surveys_to_close": surveys_to_close,
            "free_tier_limit": free_tier_limit,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        },
    )

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "user": user,
            "tier": tier,
            "tier_name": tier_display,
            "access_until_date": access_until_date,
            "survey_count": survey_count,
            "surveys_to_close": surveys_to_close,
            "free_tier_limit": free_tier_limit,
        },
    )


def send_subscription_expired_email(
    user,
    old_tier: str,
    survey_count: int = 0,
    surveys_closed: int = 0,
    reason: str = "expired",
    free_tier_limit: int = 3,
) -> bool:
    """Send notification when subscription expires or payment fails.

    This is used for:
    - Subscriptions that reached their period end date
    - Accounts downgraded due to payment failure after grace period

    Args:
        user: Django User instance
        old_tier: The tier the user was on before downgrade
        survey_count: Number of surveys user had
        surveys_closed: Number of surveys that were auto-closed
        reason: Why the subscription ended ('expired' or 'payment_failed')
        free_tier_limit: Max surveys allowed on free tier

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending subscription expired email to {user.email} "
        f"(old_tier: {old_tier}, reason: {reason})"
    )

    branding = get_platform_branding()

    tier_display = old_tier.replace("_", " ").title()

    if reason == "payment_failed":
        subject = f"Account Downgraded Due to Payment Failure - {branding['title']}"
        reason_text = (
            "We were unable to collect payment for your subscription after multiple "
            "attempts. Your account has been downgraded to the Free tier."
        )
    else:
        subject = f"Subscription Expired - {branding['title']}"
        reason_text = (
            "Your subscription has expired and your account has been "
            "downgraded to the Free tier."
        )

    # Build the email content
    markdown_lines = [
        f"# Your {tier_display} Subscription Has Ended",
        "",
        f"Hi {user.first_name or user.username},",
        "",
        reason_text,
        "",
    ]

    if surveys_closed > 0:
        markdown_lines.extend(
            [
                "## Your Surveys",
                "",
                f"Because the Free tier allows a maximum of {free_tier_limit} surveys, "
                f"we've automatically **closed** {surveys_closed} of your oldest surveys.",
                "",
                "**Closed surveys are not deleted.** You can still:",
                "- View all responses and data",
                "- Export data in any format",
                "- See all analytics and charts",
                "",
                "To reopen closed surveys, simply upgrade to a paid plan again.",
                "",
            ]
        )
    else:
        markdown_lines.extend(
            [
                f"You had {survey_count} surveys, which is within the Free tier limit of "
                f"{free_tier_limit}. All your surveys remain active.",
                "",
            ]
        )

    markdown_lines.extend(
        [
            "## Want to Continue with Premium Features?",
            "",
            "You can upgrade again at any time to restore full access to:",
            "- Unlimited surveys",
            "- Team collaboration features",
            "- Priority support",
            "- All premium features",
            "",
            f"[Upgrade Now]({getattr(settings, 'SITE_URL', 'http://localhost:8000')}/pricing/)",
            "",
            "If you have any questions, please don't hesitate to contact us.",
            "",
            "Best regards,",
            f"The {branding['title']} Team",
        ]
    )

    markdown_content = "\n".join(markdown_lines)

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "user": user,
            "old_tier": old_tier,
            "tier_name": tier_display,
            "survey_count": survey_count,
            "surveys_closed": surveys_closed,
            "reason": reason,
            "free_tier_limit": free_tier_limit,
        },
    )


def send_payment_failed_email(
    user,
    tier: str,
    failure_reason: str = "",
    grace_period_days: int = 7,
) -> bool:
    """Send notification when a subscription payment fails.

    This is sent immediately when payment fails. The user has a grace period
    to update their payment details before being downgraded.

    Args:
        user: Django User instance
        tier: Current account tier
        failure_reason: Optional reason for the failure (e.g., "insufficient funds")
        grace_period_days: Days before account is downgraded

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(f"Sending payment failed email to {user.email} (tier: {tier})")

    branding = get_platform_branding()
    tier_display = tier.replace("_", " ").title()
    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")

    subject = f"Payment Failed - Action Required - {branding['title']}"

    markdown_lines = [
        "# Payment Failed",
        "",
        f"Hi {user.first_name or user.username},",
        "",
        f"We were unable to collect your payment for your **{tier_display}** subscription.",
        "",
    ]

    if failure_reason:
        markdown_lines.extend(
            [
                f"**Reason:** {failure_reason}",
                "",
            ]
        )

    markdown_lines.extend(
        [
            "## What Happens Next",
            "",
            f"You have **{grace_period_days} days** to update your payment details. "
            "During this time, you'll retain full access to all your features.",
            "",
            f"If payment is not received within {grace_period_days} days:",
            "- Your account will be downgraded to the Free tier",
            "- Surveys exceeding the free limit will be **closed** (not deleted)",
            "- You can still view and export all your data",
            "",
            "## Update Your Payment",
            "",
            "Please update your payment details to continue enjoying your premium features:",
            "",
            f"[Update Payment Details]({site_url}/billing/subscription/)",
            "",
            "If you have any questions or need assistance, please contact us.",
            "",
            "Best regards,",
            f"The {branding['title']} Team",
        ]
    )

    markdown_content = "\n".join(markdown_lines)

    return send_branded_email(
        to_email=user.email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "user": user,
            "tier": tier,
            "tier_name": tier_display,
            "failure_reason": failure_reason,
            "grace_period_days": grace_period_days,
        },
    )


# =============================================================================
# Key Recovery Email Functions
# =============================================================================


def send_recovery_request_submitted_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    reason: str,
    estimated_review_time: str = "24-48 hours",
) -> bool:
    """Send email to user confirming their key recovery request was submitted.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        reason: User's stated reason for recovery
        estimated_review_time: Estimated time for admin review

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery request submitted email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "reason": reason,
        "estimated_review_time": estimated_review_time,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/request_submitted.md", context)
    except TemplateDoesNotExist:
        content = f"""## Key Recovery Request Submitted

Hi {user_name},

Your request to recover access to your encrypted survey data has been submitted and is pending review.

### Request Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}
- **Reason:** {reason}

### What Happens Next

1. A platform administrator will review your request
2. You may be asked to verify your identity
3. Once approved, there will be a mandatory waiting period before access is restored

**Estimated review time:** {estimated_review_time}

⚠️ **Important:** If you did not submit this request, please contact your administrator immediately.

---

Thank you for your patience.

The {branding.get("title", "CheckTick")} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"Key Recovery Request Submitted - {request_id[:8]}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_admin_notification_email(
    to_email: str,
    admin_name: str,
    request_id: str,
    requester_name: str,
    requester_email: str,
    survey_name: str,
    reason: str,
    dashboard_url: str,
) -> bool:
    """Send email to platform admin notifying them of a new recovery request.

    Args:
        to_email: Admin's email address
        admin_name: Admin's display name
        request_id: Unique recovery request ID
        requester_name: Name of user requesting recovery
        requester_email: Email of user requesting recovery
        survey_name: Name of the survey
        reason: User's stated reason for recovery
        dashboard_url: URL to recovery dashboard

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery admin notification email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "admin_name": admin_name,
        "request_id": request_id,
        "requester_name": requester_name,
        "requester_email": requester_email,
        "survey_name": survey_name,
        "reason": reason,
        "dashboard_url": dashboard_url,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/admin_notification.md", context)
    except TemplateDoesNotExist:
        content = f"""## New Key Recovery Request Requires Review

Hi {admin_name},

A new key recovery request has been submitted and requires your review.

### Request Details

- **Request ID:** `{request_id}`
- **Requester:** {requester_name} ({requester_email})
- **Survey:** {survey_name}
- **Reason:** {reason}

### Action Required

Please review this request and take appropriate action:

[**Review Request in Dashboard**]({dashboard_url})

Or copy and paste this URL:

```
{dashboard_url}
```

### Security Reminder

Before approving any recovery request:
- Verify the requester's identity through an out-of-band channel
- Review the stated reason for reasonableness
- Check for any suspicious account activity
- Document your verification steps

---

The {branding.get("title", "CheckTick")} Security Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"⚠️ Key Recovery Request Pending Review - {request_id[:8]}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_verification_needed_email(
    to_email: str,
    user_name: str,
    request_id: str,
    verification_method: str,
    verification_instructions: str,
    expires_at: str,
) -> bool:
    """Send email to user requesting identity verification.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        verification_method: Type of verification required
        verification_instructions: Instructions for verification
        expires_at: When the verification expires

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery verification needed email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "verification_method": verification_method,
        "verification_instructions": verification_instructions,
        "expires_at": expires_at,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/verification_needed.md", context)
    except TemplateDoesNotExist:
        content = f"""## Identity Verification Required

Hi {user_name},

To proceed with your key recovery request, we need to verify your identity.

### Request Details

- **Request ID:** `{request_id}`

### Verification Method

**{verification_method}**

{verification_instructions}

### Important

⏰ **This verification request expires:** {expires_at}

If you do not complete verification by this time, your recovery request will be cancelled and you'll need to submit a new one.

⚠️ **Security Note:** If you did not submit this recovery request, please contact your administrator immediately as someone may be attempting to access your data.

---

The {branding.get("title", "CheckTick")} Security Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"Identity Verification Required - Recovery Request {request_id[:8]}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_approved_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    time_delay_hours: int,
    access_available_at: str,
    approved_by: str,
) -> bool:
    """Send email to user that their recovery request was approved with time delay.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        time_delay_hours: Hours until access is granted
        access_available_at: Formatted datetime when access is available
        approved_by: Name of admin who approved

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery approved email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "time_delay_hours": time_delay_hours,
        "access_available_at": access_available_at,
        "approved_by": approved_by,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/approved.md", context)
    except TemplateDoesNotExist:
        content = f"""## Key Recovery Request Approved

Hi {user_name},

Good news! Your key recovery request has been approved.

### Request Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}
- **Approved by:** {approved_by}

### Mandatory Waiting Period

For security reasons, there is a mandatory **{time_delay_hours}-hour waiting period** before your access is restored.

⏰ **Access will be available at:** {access_available_at}

This delay helps protect against unauthorized access by giving you time to report if this request was not legitimately made by you.

### What Happens Next

1. Wait for the time delay to complete
2. You will receive another email when access is ready
3. You may then need to set a new passphrase

⚠️ **Important:** If you did not request this recovery, contact your administrator **immediately** to cancel the request during this waiting period.

---

The {branding.get("title", "CheckTick")} Security Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"✅ Key Recovery Approved - Access Available {access_available_at}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_ready_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    recovery_url: str,
) -> bool:
    """Send email to user that their recovery is complete and they can set a new passphrase.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        recovery_url: URL to complete recovery

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(f"Sending recovery ready email to {to_email} for request {request_id}")

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "recovery_url": recovery_url,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/ready.md", context)
    except TemplateDoesNotExist:
        content = f"""## Your Data Access is Ready

Hi {user_name},

The waiting period for your key recovery request has completed. You can now restore access to your encrypted data.

### Request Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}

### Complete Your Recovery

Click the link below to set a new passphrase and restore access to your data:

[**Complete Recovery**]({recovery_url})

Or copy and paste this URL:

```
{recovery_url}
```

### Important Notes

- You will need to set a new passphrase
- Your previous passphrase will no longer work
- Make sure to save your new passphrase securely

---

The {branding.get("title", "CheckTick")} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject="🔑 Your Data Access is Ready - Complete Recovery Now",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_completed_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    survey_url: str,
) -> bool:
    """Send email to user that their recovery has been completed successfully.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        survey_url: URL to access the survey

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery completed email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "survey_url": survey_url,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/completed.md", context)
    except TemplateDoesNotExist:
        content = f"""## 🎉 Recovery Complete - Access Restored

Hi {user_name},

Great news! Your key recovery request has been successfully completed. You can now access your encrypted survey data using your new password.

### Recovery Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}
- **Status:** ✅ Completed

### Access Your Survey

Your data is now accessible. Click below to open your survey:

[**Open Survey**]({survey_url})

Or copy and paste this URL:

```
{survey_url}
```

### Important Security Reminders

- **Remember your new password** - Store it securely
- **Consider setting up a recovery phrase** - This helps prevent future lockouts
- **Enable 2FA** if you haven't already

### What Happened

Your encryption keys have been recovered from our secure key escrow and re-encrypted with your new password. The original escrowed keys remain protected for future recovery needs.

### Need Help?

If you experience any issues accessing your data, please contact your administrator.

---

The {branding.get("title", "CheckTick")} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject="🎉 Recovery Complete - Your Data Access Has Been Restored",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_rejected_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    reason: str,
    rejected_by: str,
) -> bool:
    """Send email to user that their recovery request was rejected.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        reason: Reason for rejection
        rejected_by: Name of admin who rejected

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery rejected email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "reason": reason,
        "rejected_by": rejected_by,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/rejected.md", context)
    except TemplateDoesNotExist:
        content = f"""## Key Recovery Request Rejected

Hi {user_name},

Unfortunately, your key recovery request has been rejected.

### Request Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}
- **Reviewed by:** {rejected_by}

### Reason for Rejection

{reason}

### What You Can Do

If you believe this rejection was made in error, you can:

1. Contact your organization administrator
2. Submit a new recovery request with additional information
3. Verify your identity through your organization's IT support

---

The {branding.get("title", "CheckTick")} Security Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"❌ Key Recovery Request Rejected - {request_id[:8]}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_cancelled_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    cancelled_by: str,
    reason: str = "",
) -> bool:
    """Send email to user that their recovery request was cancelled.

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        cancelled_by: Who cancelled the request
        reason: Optional reason for cancellation

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery cancelled email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "cancelled_by": cancelled_by,
        "reason": reason,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/cancelled.md", context)
    except TemplateDoesNotExist:
        reason_line = f"- **Reason:** {reason}" if reason else ""
        content = f"""## Key Recovery Request Cancelled

Hi {user_name},

Your key recovery request has been cancelled.

### Request Details

- **Request ID:** `{request_id}`
- **Survey:** {survey_name}
- **Cancelled by:** {cancelled_by}
{reason_line}

### Need Help?

If you still need to recover access to your data, you can submit a new recovery request.

If you have questions about why this request was cancelled, please contact your administrator.

---

The {branding.get("title", "CheckTick")} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=f"Key Recovery Request Cancelled - {request_id[:8]}",
        markdown_content=content,
        branding=branding,
    )


def send_recovery_security_alert_email(
    to_email: str,
    user_name: str,
    request_id: str,
    survey_name: str,
    alert_type: str,
    alert_details: str,
    action_url: str,
) -> bool:
    """Send security alert email about a recovery request (e.g., suspicious activity).

    Args:
        to_email: Recipient email address
        user_name: User's display name
        request_id: Unique recovery request ID
        survey_name: Name of the survey
        alert_type: Type of security alert
        alert_details: Details about the alert
        action_url: URL to take action

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Sending recovery security alert email to {to_email} for request {request_id}"
    )

    branding = get_platform_branding()

    context = {
        "user_name": user_name,
        "request_id": request_id,
        "survey_name": survey_name,
        "alert_type": alert_type,
        "alert_details": alert_details,
        "action_url": action_url,
        "brand_title": branding.get("title", "CheckTick"),
    }

    try:
        content = render_to_string("emails/recovery/security_alert.md", context)
    except TemplateDoesNotExist:
        content = f"""## 🚨 Security Alert: Key Recovery Request

Hi {user_name},

We detected potentially suspicious activity related to a key recovery request on your account.

### Alert Details

- **Alert Type:** {alert_type}
- **Request ID:** `{request_id}`
- **Survey:** {survey_name}

### What Happened

{alert_details}

### Take Action

If you **did not** initiate this recovery request, take immediate action:

[**Report Unauthorized Access**]({action_url})

Or copy and paste this URL:

```
{action_url}
```

### If This Was You

If you did initiate this request, you can safely ignore this alert. This notification is sent as a security precaution.

### Contact Support

If you have any concerns about your account security, please contact your administrator immediately.

---

The {branding.get("title", "CheckTick")} Security Team
"""

    return send_branded_email(
        to_email=to_email,
        subject="🚨 Security Alert: Key Recovery Request on Your Account",
        markdown_content=content,
        branding=branding,
    )


# =============================================================================
# Team and Organization Invitation Email Functions
# =============================================================================


def send_team_invitation_email(
    to_email: str,
    team,
    role: str,
    invited_by,
) -> bool:
    """Send team invitation email to a new user.

    Args:
        to_email: Recipient email address (no existing account)
        team: Team object
        role: Role being offered (admin, creator, viewer)
        invited_by: User who sent the invitation

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.conf import settings

    logger.info(
        f"Attempting to send team invitation email to {to_email} for team: {team.name}"
    )

    branding = get_platform_branding()

    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    signup_link = f"{site_url}/signup/?email={to_email}"

    # Get organization name if team is part of one
    organization_name = None
    if team.organization:
        organization_name = team.organization.name

    role_display = role.title()
    subject = f"You're invited to join {team.name}"

    try:
        markdown_content = render_to_string(
            "emails/team_invitation.md",
            {
                "team_name": team.name,
                "role": role,
                "role_display": role_display,
                "invited_by_name": invited_by.get_full_name() or invited_by.username,
                "invited_by_email": invited_by.email,
                "signup_link": signup_link,
                "organization_name": organization_name,
                "brand_title": branding["title"],
            },
        )
    except TemplateDoesNotExist:
        org_line = f"as part of **{organization_name}** " if organization_name else ""
        markdown_content = f"""## You're Invited to Join {team.name}

Hi there,

**{invited_by.get_full_name() or invited_by.username}** has invited you to join their team on {branding["title"]}.

### Invitation Details

- **Team:** {team.name}
- **Your Role:** {role_display}
- **Invited by:** {invited_by.get_full_name() or invited_by.username} ({invited_by.email})

{org_line}

### Get Started

To accept this invitation and join the team, create your account:

[**Create Account**]({signup_link})

Or copy and paste this URL:

```
{signup_link}
```

Once you create your account with **{to_email}**, you'll automatically be added to the team.

### What You'll Be Able to Do

As a **{role_display}**, you'll be able to:
{"- Manage team settings and members" if role == "admin" else ""}
{"- Create and edit surveys" if role in ("admin", "creator") else ""}
- View team surveys and data

---

If you have any questions, please contact {invited_by.email}.

The {branding["title"]} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "team_name": team.name,
            "role": role,
            "invited_by": invited_by,
            "signup_link": signup_link,
        },
    )


def send_org_invitation_email(
    to_email: str,
    organization,
    role: str,
    invited_by,
) -> bool:
    """Send organization invitation email to a new user.

    Args:
        to_email: Recipient email address (no existing account)
        organization: Organization object
        role: Role being offered (admin, creator, viewer)
        invited_by: User who sent the invitation

    Returns:
        True if email sent successfully, False otherwise
    """
    from django.conf import settings

    logger.info(
        f"Attempting to send organization invitation email to {to_email} for org: {organization.name}"
    )

    branding = get_platform_branding()

    site_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    signup_link = f"{site_url}/signup/?email={to_email}"

    role_display = role.title()
    subject = f"You're invited to join {organization.name}"

    try:
        markdown_content = render_to_string(
            "emails/org_invitation.md",
            {
                "org_name": organization.name,
                "role": role,
                "role_display": role_display,
                "invited_by_name": invited_by.get_full_name() or invited_by.username,
                "invited_by_email": invited_by.email,
                "signup_link": signup_link,
                "brand_title": branding["title"],
            },
        )
    except TemplateDoesNotExist:
        markdown_content = f"""## You're Invited to Join {organization.name}

Hi there,

**{invited_by.get_full_name() or invited_by.username}** has invited you to join their organization on {branding["title"]}.

### Invitation Details

- **Organization:** {organization.name}
- **Your Role:** {role_display}
- **Invited by:** {invited_by.get_full_name() or invited_by.username} ({invited_by.email})

### Get Started

To accept this invitation and join the organization, create your account:

[**Create Account**]({signup_link})

Or copy and paste this URL:

```
{signup_link}
```

Once you create your account with **{to_email}**, you'll automatically be added to the organization.

### What You'll Be Able to Do

As a **{role_display}**, you'll be able to:
{"- Manage organization settings, teams, and members" if role == "admin" else ""}
{"- Create and edit surveys across the organization" if role in ("admin", "creator") else ""}
- View organization surveys and data
- Collaborate with team members

---

If you have any questions, please contact {invited_by.email}.

The {branding["title"]} Team
"""

    return send_branded_email(
        to_email=to_email,
        subject=subject,
        markdown_content=markdown_content,
        branding=branding,
        context={
            "org_name": organization.name,
            "role": role,
            "invited_by": invited_by,
            "signup_link": signup_link,
        },
    )
