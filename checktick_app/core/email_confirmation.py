from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string

from .email_utils import get_platform_branding, send_branded_email
from .models import SiteBranding, UserProfile

logger = logging.getLogger(__name__)

User = get_user_model()


class EmailConfirmationManager:
    """Manages email confirmation tokens and verification for users."""

    @staticmethod
    def generate_token():
        """Generate a random token for email confirmation."""
        return get_random_string(32)

    @staticmethod
    def send_confirmation_email(user, request=None):
        """Send email confirmation to user.

        Returns:
            tuple: (token, success, error_info) where success is boolean
                   and error_info contains details about any delivery issues
        """
        # Create or update confirmation token in user profile
        token = EmailConfirmationManager.generate_token()
        expires_at = timezone.now() + timedelta(hours=24)

        user.profile.email_confirmation_token = token
        user.profile.email_confirmation_token_expires = expires_at
        user.profile.save(
            update_fields=[
                "email_confirmation_token",
                "email_confirmation_token_expires",
            ]
        )

        # Get branding info (colours, fonts, logo) for the branded wrapper
        try:
            branding = get_platform_branding()
        except Exception:
            branding = None

        # Ensure a SiteBranding row exists (legacy behaviour: some flows
        # expect the singleton row to be present after signup).
        if not SiteBranding.objects.filter(pk=1).exists():
            SiteBranding.objects.create(pk=1)

        # Build confirmation URL
        if request:
            base_url = f"{request.scheme}://{request.get_host()}"
        else:
            base_url = getattr(settings, "SITE_URL", "https://checktick.example.com")

        confirmation_url = f"{base_url}/accounts/confirm-email/{token}/"

        # Render email content
        context = {
            "user": user,
            "confirmation_url": confirmation_url,
            "brand_title": settings.BRAND_TITLE,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        subject = f"Please confirm your email address - {settings.BRAND_TITLE}"

        try:
            markdown_content = render_to_string("emails/confirm_email.md", context)
            sent = send_branded_email(
                to_email=user.email,
                subject=subject,
                markdown_content=markdown_content,
                branding=branding,
                context=context,
            )
            if not sent:
                raise RuntimeError("send_branded_email reported failure")
            return token, True, None
        except Exception as e:
            # Log the specific error for debugging
            error_info = {
                "type": type(e).__name__,
                "message": str(e),
                "email": user.email,
            }
            logger.warning(
                "Email confirmation delivery failed",
                extra={
                    "email": user.email,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return token, False, error_info

    @staticmethod
    def verify_token(token):
        """Verify an email confirmation token."""
        try:
            # Look for token in user profiles instead
            user_profile = UserProfile.objects.select_related("user").get(
                email_confirmation_token=token,
                email_confirmation_token_expires__gt=timezone.now(),
            )

            user = user_profile.user
            user.profile.email_confirmed = True
            # Clear the token fields after successful confirmation
            user.profile.email_confirmation_token = None
            user.profile.email_confirmation_token_expires = None
            user.profile.save(
                update_fields=[
                    "email_confirmed",
                    "email_confirmation_token",
                    "email_confirmation_token_expires",
                ]
            )

            return user
        except UserProfile.DoesNotExist:
            return None
