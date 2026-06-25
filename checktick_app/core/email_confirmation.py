import uuid
from calendar import c
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import SiteBranding

User = get_user_model()


class EmailConfirmationManager:
    """Manages email confirmation tokens and verification for users."""

    @staticmethod
    def generate_token():
        """Generate a random token for email confirmation."""
        return get_random_string(32)

    @staticmethod
    def send_confirmation_email(user, request=None):
        """Send email confirmation to user."""
        from .email_confirmation import EmailConfirmationToken

        # Create or update confirmation token
        confirmation, created = EmailConfirmationToken.objects.get_or_create(
            user=user,
            defaults={
                "token": EmailConfirmationManager.generate_token(),
                "expires_at": timezone.now() + timedelta(hours=24),
            },
        )

        if not created:
            # Update the token and expiry if it already exists
            confirmation.token = EmailConfirmationManager.generate_token()
            confirmation.expires_at = timezone.now() + timedelta(hours=24)
            confirmation.save()

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

        confirmation_url = f"{base_url}/accounts/confirm-email/{confirmation.token}/"

        # Render email content
        context = {
            "user": user,
            "confirmation_url": confirmation_url,
            "brand_title": settings.BRAND_TITLE,
            "expires_at": confirmation.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        subject = f"Please confirm your email address - {settings.BRAND_TITLE}"
        html_message = render_to_string("emails/confirm_email.html", context)
        text_message = render_to_string("emails/confirm_email.txt", context)

        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=not settings.DEBUG,
        )

        return confirmation

    @staticmethod
    def verify_token(token):
        """Verify an email confirmation token."""
        from .email_confirmation import EmailConfirmationToken

        try:
            confirmation = EmailConfirmationToken.objects.select_related("user").get(
                token=token, expires_at__gt=timezone.now()
            )

            user = confirmation.user
            user.profile.email_confirmed = True
            user.profile.save(update_fields=["email_confirmed"])

            # Mark this confirmation as used
            confirmation.delete()

            return user
        except EmailConfirmationToken.DoesNotExist:
            return None


class EmailConfirmationToken(models.Model):
    """Model to store email confirmation tokens."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="email_confirmation_token"
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "email_confirmation_token"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self):
        """Check if the confirmation token has expired."""
        return self.expires_at < timezone.now()
