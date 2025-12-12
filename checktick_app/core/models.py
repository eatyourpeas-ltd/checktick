from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

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
        default="",
        help_text="DaisyUI preset theme for light mode (e.g., 'nord', 'cupcake', 'light'). Defaults to BRAND_THEME_PRESET_LIGHT setting.",
    )
    theme_preset_dark = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="DaisyUI preset theme for dark mode (e.g., 'business', 'dark', 'synthwave'). Defaults to BRAND_THEME_PRESET_DARK setting.",
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


class UserProfile(models.Model):
    """User account tier and payment information.

    Manages account tiers, payment tracking, and enterprise branding features.
    Every user has one profile (created automatically on signup).
    """

    # Account tiers
    class AccountTier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Professional"
        TEAM_SMALL = "team_small", "Team Small"
        TEAM_MEDIUM = "team_medium", "Team Medium"
        TEAM_LARGE = "team_large", "Team Large"
        ORGANIZATION = "organization", "Organization"
        ENTERPRISE = "enterprise", "Enterprise"

    # Payment subscription status
    class SubscriptionStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        TRIALING = "trialing", "Trialing"
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
        UNPAID = "unpaid", "Unpaid"
        NONE = "none", "None"  # For FREE tier or self-hosted

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Account tier and limits
    account_tier = models.CharField(
        max_length=20,
        choices=AccountTier.choices,
        default=AccountTier.FREE,
        help_text="Current account tier determining feature access",
    )

    # Payment tracking (generic provider-agnostic)
    payment_provider = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Payment provider name (e.g., 'ryft', 'stripe')",
    )
    payment_customer_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Customer ID from payment provider",
    )
    payment_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Subscription ID from payment provider",
    )
    payment_mandate_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Mandate ID from payment provider (GoCardless)",
    )
    subscription_status = models.CharField(
        max_length=30,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.NONE,
        help_text="Current subscription status",
    )
    subscription_current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current subscription period ends",
    )

    # Enterprise branding (UI-based, only for Enterprise tier or self-hosted)
    custom_branding_enabled = models.BooleanField(
        default=False,
        help_text="Whether user can customize platform branding (Enterprise only)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tier_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the account tier was last changed",
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username} - {self.get_account_tier_display()}"

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create profile for a user with defaults."""
        profile, created = cls.objects.get_or_create(user=user)
        return profile

    def get_effective_tier(self) -> str:
        """Get the effective account tier considering self-hosted mode.

        In self-hosted mode (SELF_HOSTED=true), all users get Enterprise features.
        Otherwise, returns the actual account tier.
        """
        if getattr(settings, "SELF_HOSTED", False):
            return self.AccountTier.ENTERPRISE
        return self.account_tier

    def is_tier_at_least(self, tier: str) -> bool:
        """Check if user's effective tier is at least the specified tier.

        Tier hierarchy: FREE < PRO < ORGANIZATION < ENTERPRISE
        """
        tier_order = {
            self.AccountTier.FREE: 0,
            self.AccountTier.PRO: 1,
            self.AccountTier.ORGANIZATION: 2,
            self.AccountTier.ENTERPRISE: 3,
        }
        effective = self.get_effective_tier()
        return tier_order.get(effective, 0) >= tier_order.get(tier, 0)

    def can_create_survey(self) -> tuple[bool, str]:
        """Check if user can create a new survey.

        Returns:
            (can_create, reason) - tuple with boolean and error message
        """
        from .tier_limits import check_survey_creation_limit

        return check_survey_creation_limit(self.user)

    def can_add_collaborators(
        self, collaboration_type: str = "editor"
    ) -> tuple[bool, str]:
        """Check if user can add collaborators to surveys.

        Args:
            collaboration_type: 'editor' or 'viewer'

        Returns:
            (can_add, reason) - tuple with boolean and error message
        """
        from .tier_limits import check_collaboration_limit

        return check_collaboration_limit(self.user, collaboration_type)

    def can_customize_branding(self) -> tuple[bool, str]:
        """Check if user can customize platform branding.

        Returns:
            (can_customize, reason) - tuple with boolean and error message
        """
        from .tier_limits import check_branding_permission

        return check_branding_permission(self.user)

    def can_create_sub_organizations(self) -> tuple[bool, str]:
        """Check if user can create sub-organizations.

        Returns:
            (can_create, reason) - tuple with boolean and error message
        """
        from .tier_limits import check_sub_organization_permission

        return check_sub_organization_permission(self.user)

    def upgrade_tier(self, new_tier: str) -> None:
        """Upgrade user to a new tier.

        Args:
            new_tier: The new tier to upgrade to
        """
        if new_tier in self.AccountTier.values:
            self.account_tier = new_tier
            self.tier_changed_at = timezone.now()
            self.save(update_fields=["account_tier", "tier_changed_at", "updated_at"])

    def downgrade_tier(self, new_tier: str) -> tuple[bool, str]:
        """Downgrade user to a lower tier.

        Validates that user meets requirements for the target tier before downgrading.
        For example, FREE tier users cannot have more than 3 surveys.

        Args:
            new_tier: The new tier to downgrade to

        Returns:
            (success, message) - Boolean indicating success and message explaining result
        """
        if new_tier not in self.AccountTier.values:
            return False, f"Invalid tier: {new_tier}"

        # Check if downgrade is allowed based on current usage
        from checktick_app.core.tier_limits import get_tier_limits
        from checktick_app.surveys.models import Survey

        target_limits = get_tier_limits(new_tier)

        # Check survey count if target tier has a limit
        if target_limits.max_surveys is not None:
            survey_count = Survey.objects.filter(
                owner=self.user, is_original=True
            ).count()
            if survey_count > target_limits.max_surveys:
                return False, (
                    f"Cannot downgrade to {new_tier.title()} tier: You currently have "
                    f"{survey_count} surveys, but {new_tier.title()} tier allows a maximum of "
                    f"{target_limits.max_surveys}. Please delete or archive "
                    f"{survey_count - target_limits.max_surveys} survey(s) before downgrading."
                )

        # Downgrade is allowed
        self.account_tier = new_tier
        self.tier_changed_at = timezone.now()
        self.save(update_fields=["account_tier", "tier_changed_at", "updated_at"])
        return True, f"Successfully downgraded to {new_tier.title()} tier"

    def force_downgrade_tier(self, new_tier: str) -> tuple[bool, str]:
        """Force downgrade to a lower tier, auto-closing excess surveys.

        This is used when a subscription is canceled. If the user has more surveys
        than the target tier allows, the oldest surveys will be automatically closed
        (status set to 'closed'). Closed surveys remain read-only - users can view
        and export data but cannot edit or publish them.

        Args:
            new_tier: The new tier to downgrade to

        Returns:
            (success, message) - Boolean indicating success and message explaining result
        """
        if new_tier not in self.AccountTier.values:
            return False, f"Invalid tier: {new_tier}"

        from checktick_app.core.tier_limits import get_tier_limits
        from checktick_app.surveys.models import Survey

        target_limits = get_tier_limits(new_tier)

        # Auto-close excess surveys if target tier has a survey limit
        surveys_closed = 0
        if target_limits.max_surveys is not None:
            # Get all active/draft surveys ordered by created_at (oldest first)
            active_surveys = (
                Survey.objects.filter(
                    owner=self.user,
                )
                .exclude(status=Survey.Status.CLOSED)
                .order_by("created_at")
            )

            survey_count = active_surveys.count()
            if survey_count > target_limits.max_surveys:
                # Close the oldest excess surveys
                excess_count = survey_count - target_limits.max_surveys
                surveys_to_close = active_surveys[:excess_count]

                for survey in surveys_to_close:
                    survey.status = Survey.Status.CLOSED
                    survey.save(update_fields=["status"])
                    surveys_closed += 1

        # Perform the downgrade
        self.account_tier = new_tier
        self.tier_changed_at = timezone.now()
        self.save(update_fields=["account_tier", "tier_changed_at", "updated_at"])

        if surveys_closed > 0:
            return True, (
                f"Downgraded to {new_tier.title()} tier. {surveys_closed} survey(s) "
                f"automatically closed (oldest first). You can still view and export "
                f"data from closed surveys."
            )
        return True, f"Successfully downgraded to {new_tier.title()} tier"

    def update_subscription(
        self,
        subscription_id: str,
        status: str,
        current_period_end: timezone.datetime = None,
    ) -> None:
        """Update subscription information from payment provider webhook.

        Args:
            subscription_id: Subscription ID from provider
            status: Subscription status
            current_period_end: When the current period ends
        """
        self.payment_subscription_id = subscription_id
        self.subscription_status = status
        if current_period_end:
            self.subscription_current_period_end = current_period_end
        self.save(
            update_fields=[
                "payment_subscription_id",
                "subscription_status",
                "subscription_current_period_end",
                "updated_at",
            ]
        )


class Payment(models.Model):
    """Record of payment transactions for VAT reporting and audit trail.

    Each successful payment creates a record here for quarterly VAT returns.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    # Link to user
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
        help_text="User who made the payment",
    )

    # Invoice details
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique invoice number for VAT purposes",
    )
    invoice_date = models.DateField(help_text="Date of invoice")

    # Payment details
    payment_provider = models.CharField(
        max_length=50,
        default="gocardless",
        help_text="Payment provider (gocardless, manual, etc.)",
    )
    payment_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Payment ID from provider",
    )
    subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subscription ID from provider",
    )

    # Tier and billing period
    tier = models.CharField(
        max_length=20,
        help_text="Subscription tier at time of payment",
    )
    billing_period_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start of billing period",
    )
    billing_period_end = models.DateField(
        null=True,
        blank=True,
        help_text="End of billing period",
    )

    # Amounts (stored in pence/minor currency units)
    amount_ex_vat = models.IntegerField(help_text="Amount excluding VAT in pence")
    vat_amount = models.IntegerField(help_text="VAT amount in pence")
    amount_inc_vat = models.IntegerField(
        help_text="Total amount including VAT in pence"
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.20,
        help_text="VAT rate applied (e.g., 0.20 for 20%)",
    )
    currency = models.CharField(max_length=3, default="GBP")

    # Customer details at time of payment (for invoice)
    customer_email = models.EmailField(help_text="Customer email at time of payment")
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Customer name/username",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was confirmed",
    )

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-invoice_date", "-created_at"]
        indexes = [
            models.Index(fields=["invoice_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.invoice_number} - £{self.amount_inc_vat / 100:.2f} ({self.status})"
        )

    @classmethod
    def generate_invoice_number(cls) -> str:
        """Generate a unique invoice number.

        Format: INV-YYYYMMDD-XXXXXXXX
        """
        import uuid
        from datetime import date

        today = date.today()
        unique_part = uuid.uuid4().hex[:8].upper()
        return f"INV-{today.strftime('%Y%m%d')}-{unique_part}"

    @classmethod
    def create_from_subscription(
        cls,
        user,
        tier: str,
        payment_id: str = "",
        subscription_id: str = "",
        billing_period_start=None,
        billing_period_end=None,
    ):
        """Create a payment record from a subscription confirmation.

        Args:
            user: Django User instance
            tier: Subscription tier
            payment_id: Payment ID from provider
            subscription_id: Subscription ID from provider
            billing_period_start: Start of billing period
            billing_period_end: End of billing period

        Returns:
            Payment instance
        """
        from datetime import date

        from django.conf import settings

        # Get tier pricing
        tier_config = getattr(settings, "SUBSCRIPTION_TIERS", {}).get(tier, {})
        amount_ex_vat = tier_config.get("amount_ex_vat", 0)
        amount_inc_vat = tier_config.get("amount", 0)
        vat_amount = amount_inc_vat - amount_ex_vat
        vat_rate = getattr(settings, "VAT_RATE", 0.20)

        return cls.objects.create(
            user=user,
            invoice_number=cls.generate_invoice_number(),
            invoice_date=date.today(),
            payment_provider="gocardless",
            payment_id=payment_id,
            subscription_id=subscription_id,
            tier=tier,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            amount_ex_vat=amount_ex_vat,
            vat_amount=vat_amount,
            amount_inc_vat=amount_inc_vat,
            vat_rate=vat_rate,
            currency=tier_config.get("currency", "GBP"),
            customer_email=user.email,
            customer_name=user.get_full_name() or user.username,
            status=cls.PaymentStatus.CONFIRMED,
            confirmed_at=timezone.now(),
        )

    def get_amount_ex_vat_display(self) -> str:
        """Return formatted amount excluding VAT."""
        return f"£{self.amount_ex_vat / 100:.2f}"

    def get_vat_amount_display(self) -> str:
        """Return formatted VAT amount."""
        return f"£{self.vat_amount / 100:.2f}"

    def get_amount_inc_vat_display(self) -> str:
        """Return formatted total amount."""
        return f"£{self.amount_inc_vat / 100:.2f}"

    def get_vat_rate_display(self) -> str:
        """Return formatted VAT rate."""
        return f"{float(self.vat_rate) * 100:.0f}%"
