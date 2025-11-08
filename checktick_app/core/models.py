from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SiteBranding(models.Model):
    """Singleton-ish model storing project-level branding and theme overrides.

    Use get_or_create(pk=1) to manage a single row.
    """

    DEFAULT_THEME_CHOICES = [
        ("checktick-light", "CheckTick Light"),
        ("checktick-dark", "CheckTick Dark"),
    ]

    default_theme = models.CharField(
        max_length=64, choices=DEFAULT_THEME_CHOICES, default="checktick-light"
    )
    icon_url = models.URLField(blank=True, default="")
    icon_file = models.FileField(upload_to="branding/", blank=True, null=True)
    # Optional dark icon variants
    icon_url_dark = models.URLField(blank=True, default="")
    icon_file_dark = models.FileField(upload_to="branding/", blank=True, null=True)
    font_heading = models.CharField(max_length=512, blank=True, default="")
    font_body = models.CharField(max_length=512, blank=True, default="")
    font_css_url = models.URLField(blank=True, default="")

    # DaisyUI preset theme selections (generates CSS from these)
    theme_preset_light = models.CharField(
        max_length=64,
        blank=True,
        default="wireframe",
        help_text="DaisyUI preset theme for light mode (e.g., 'wireframe', 'cupcake', 'light')",
    )
    theme_preset_dark = models.CharField(
        max_length=64,
        blank=True,
        default="business",
        help_text="DaisyUI preset theme for dark mode (e.g., 'business', 'dark', 'synthwave')",
    )

    # Raw CSS variable declarations for themes, after normalization to DaisyUI runtime vars
    # These are generated from theme_preset_* or can be custom CSS from daisyUI theme builder
    theme_light_css = models.TextField(blank=True, default="")
    theme_dark_css = models.TextField(blank=True, default="")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"Site Branding (theme={self.default_theme})"


class UserEmailPreferences(models.Model):
    """User preferences for email notifications.

    Each user has one preferences object (created on demand).
    Controls granularity of email notifications for various system events.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="email_preferences"
    )

    # Account-related emails (always sent regardless of preferences for security)
    send_welcome_email = models.BooleanField(
        default=True,
        help_text="Send welcome email when account is created (recommended)",
    )
    send_password_change_email = models.BooleanField(
        default=True,
        help_text="Send notification when password is changed (security feature)",
    )

    # Survey-related emails (optional)
    send_survey_created_email = models.BooleanField(
        default=False,
        help_text="Send notification when you create a new survey",
    )
    send_survey_deleted_email = models.BooleanField(
        default=False,
        help_text="Send notification when you delete a survey",
    )
    send_survey_published_email = models.BooleanField(
        default=False,
        help_text="Send notification when a survey is published",
    )

    # Organization/team emails
    send_team_invitation_email = models.BooleanField(
        default=True,
        help_text="Send notification when you're invited to an organization",
    )
    send_survey_invitation_email = models.BooleanField(
        default=True,
        help_text="Send notification when you're added to a survey team",
    )

    # Future: logging-related notifications (for integration with logging system)
    # These will be used when logging/signals feature is implemented
    notify_on_error = models.BooleanField(
        default=True,
        help_text="Send email notifications for system errors affecting your surveys",
    )
    notify_on_critical = models.BooleanField(
        default=True,
        help_text="Send email notifications for critical issues",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Email Preference"
        verbose_name_plural = "User Email Preferences"

    def __str__(self) -> str:  # pragma: no cover
        return f"Email Preferences for {self.user.username}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create email preferences for a user with defaults."""
        preferences, created = cls.objects.get_or_create(user=user)
        return preferences


class UserLanguagePreference(models.Model):
    """User language preference for interface localization.

    Stores the user's preferred language for the application UI.
    Used by custom middleware to set the active language.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="language_preference"
    )
    language = models.CharField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        help_text="Preferred language for the application interface",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Language Preference"
        verbose_name_plural = "User Language Preferences"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username}: {self.get_language_display()}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create language preference for a user with default."""
        preference, created = cls.objects.get_or_create(
            user=user, defaults={"language": settings.LANGUAGE_CODE}
        )
        return preference


class UserOIDC(models.Model):
    """OIDC authentication details for users who authenticate via SSO.

    This model stores OIDC-specific information for users who authenticate
    through OpenID Connect providers (Google, Azure AD, etc.).
    Only created for users who use OIDC authentication.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="oidc")
    provider = models.CharField(
        max_length=100, help_text="OIDC provider identifier (e.g., 'google', 'azure')"
    )
    subject = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique subject identifier from the OIDC provider",
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the email address has been verified by the OIDC provider",
    )
    signup_completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed the signup process (account type selection, etc.)",
    )
    key_derivation_salt = models.BinaryField(
        help_text="Unique salt for deriving encryption keys from OIDC identity"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User OIDC Authentication"
        verbose_name_plural = "User OIDC Authentications"
        indexes = [
            models.Index(fields=["provider", "subject"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username} ({self.provider})"

    @classmethod
    def get_or_create_for_user(cls, user, provider, subject, email_verified=False):
        """Get or create OIDC record for a user with default salt generation."""
        import os

        oidc_record, created = cls.objects.get_or_create(
            user=user,
            defaults={
                "provider": provider,
                "subject": subject,
                "email_verified": email_verified,
                "key_derivation_salt": os.urandom(32),
            },
        )
        return oidc_record, created
