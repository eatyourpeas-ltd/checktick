"""Email utilities for sending branded, themed emails.

Supports both platform-level branding (for account emails) and survey-level
theming (for survey-specific emails).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
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
) -> bool:
    """Send survey invitation email with unique token link.

    Args:
        to_email: Recipient email address
        survey: Survey object
        token: Unique access token string
        contact_email: Optional contact email for questions

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
        },
    )


def send_authenticated_survey_invite_existing_user(
    to_email: str,
    survey,
    contact_email: Optional[str] = None,
) -> bool:
    """Send survey invitation to existing authenticated user.

    Args:
        to_email: Recipient email address (existing user)
        survey: Survey object
        contact_email: Optional contact email for questions

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
        },
    )


def send_authenticated_survey_invite_new_user(
    to_email: str,
    survey,
    contact_email: Optional[str] = None,
) -> bool:
    """Send survey invitation to new user (needs to create account).

    Args:
        to_email: Recipient email address (no existing account)
        survey: Survey object
        contact_email: Optional contact email for questions

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
        },
    )


def send_subscription_created_email(
    user, tier: str, billing_cycle: str = "Monthly"
) -> bool:
    """Send welcome email when user subscribes to a paid plan.

    Args:
        user: Django User instance
        tier: Account tier (pro, enterprise)
        billing_cycle: Billing cycle (Monthly, Yearly)

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Attempting to send subscription created email to {user.email} (username: {user.username}, tier: {tier}, cycle: {billing_cycle})"
    )

    branding = get_platform_branding()

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
