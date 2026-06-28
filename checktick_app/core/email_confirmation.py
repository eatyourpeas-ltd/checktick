import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string

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

        # Get branding info
        branding = SiteBranding.objects.first()
        if not branding:
            # Create default branding if it doesn't exist
            branding = SiteBranding.objects.create(pk=1)

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
        html_message = render_to_string("emails/confirm_email.html", context)
        text_message = render_to_string("emails/confirm_email.txt", context)

        try:
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=not settings.DEBUG,
            )
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
