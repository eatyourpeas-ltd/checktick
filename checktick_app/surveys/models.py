from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .utils import decrypt_sensitive, encrypt_sensitive, make_key_hash

User = get_user_model()


def get_default_retention_months():
    """Get default retention months from settings."""
    return getattr(settings, "CHECKTICK_DEFAULT_RETENTION_MONTHS", 6)


class Organization(models.Model):
    DEFAULT_THEME_CHOICES = [
        ("checktick-light", "CheckTick Light"),
        ("checktick-dark", "CheckTick Dark"),
    ]

    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="organizations"
    )
    # Organization master key for encrypting member surveys (Option 1: Key Escrow)
    # In production, this should be encrypted with AWS KMS or Azure Key Vault
    # For now, storing as plaintext for development/testing
    encrypted_master_key = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Organization master key for administrative recovery of member surveys",
    )

    # Organization-level theme settings (overrides platform defaults)
    default_theme = models.CharField(
        max_length=64,
        choices=DEFAULT_THEME_CHOICES,
        blank=True,
        default="",
        help_text="Default theme for organization (empty = use platform default)",
    )
    theme_preset_light = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="DaisyUI preset for light mode (empty = use platform default)",
    )
    theme_preset_dark = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="DaisyUI preset for dark mode (empty = use platform default)",
    )
    theme_light_css = models.TextField(
        blank=True,
        default="",
        help_text="Custom CSS for light theme (overrides preset if provided)",
    )
    theme_dark_css = models.TextField(
        blank=True,
        default="",
        help_text="Custom CSS for dark theme (overrides preset if provided)",
    )

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CREATOR = "creator", "Creator"
        VIEWER = "viewer", "Viewer"
        DATA_CUSTODIAN = "data_custodian", "Data Custodian"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="org_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CREATOR)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "user")


class QuestionGroup(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="question_groups"
    )
    shared = models.BooleanField(default=False)
    schema = models.JSONField(
        default=dict, help_text="Definition of questions in this group"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Survey(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="surveys")
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    question_groups = models.ManyToManyField(
        QuestionGroup, blank=True, related_name="surveys"
    )
    # Per-survey style overrides (title, theme_name, icon_url, font_heading, font_body, primary_color)
    style = models.JSONField(default=dict, blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    class Visibility(models.TextChoices):
        AUTHENTICATED = "authenticated", "Authenticated users only"
        PUBLIC = "public", "Public"
        UNLISTED = "unlisted", "Unlisted (secret link)"
        TOKEN = "token", "By invite token"

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.AUTHENTICATED
    )
    published_at = models.DateTimeField(null=True, blank=True)
    unlisted_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    max_responses = models.PositiveIntegerField(null=True, blank=True)
    captcha_required = models.BooleanField(default=False)
    no_patient_data_ack = models.BooleanField(
        default=False,
        help_text="Publisher confirms no patient data is collected when using non-authenticated visibility",
    )
    # One-time survey key: store only hash + salt for verification
    key_salt = models.BinaryField(blank=True, null=True, editable=False)
    key_hash = models.BinaryField(blank=True, null=True, editable=False)
    # Option 2: Dual-path encryption for individual users
    encrypted_kek_password = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Survey encryption key encrypted with password-derived key",
    )
    encrypted_kek_recovery = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Survey encryption key encrypted with recovery-phrase-derived key",
    )
    recovery_code_hint = models.CharField(
        max_length=255,
        blank=True,
        help_text="First and last word of recovery phrase (e.g., 'apple...zebra')",
    )
    # Option 3: OIDC-derived encryption for SSO users
    encrypted_kek_oidc = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Survey encryption key encrypted with OIDC-derived key for automatic unlock",
    )
    # Option 1: Organization-level key escrow
    encrypted_kek_org = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Survey encryption key encrypted with organization master key for administrative recovery",
    )
    recovery_threshold = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Number of recovery admins required for Shamir's Secret Sharing (optional)",
    )
    recovery_shares_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Total number of recovery shares distributed (optional, for Shamir's Secret Sharing)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Data Governance fields
    # Survey closure
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the survey was closed (starts retention period)",
    )
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_surveys",
        help_text="User who closed the survey",
    )

    # Retention
    retention_months = models.IntegerField(
        default=get_default_retention_months,
        help_text="Retention period in months (configurable via CHECKTICK_DEFAULT_RETENTION_MONTHS)",
    )
    deletion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when survey data will be automatically deleted",
    )

    # Soft deletion (30-day grace period)
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When survey was soft deleted (30-day grace period)",
    )
    hard_deletion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When survey will be permanently deleted",
    )

    # Ownership transfer
    transferred_from = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transferred_surveys",
        help_text="Previous owner if ownership was transferred",
    )
    transferred_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When ownership was transferred",
    )

    def is_live(self) -> bool:
        now = timezone.now()
        time_ok = (self.start_at is None or self.start_at <= now) and (
            self.end_at is None or now <= self.end_at
        )
        status_ok = self.status == self.Status.PUBLISHED
        # Respect max responses if set
        if self.max_responses is not None and hasattr(self, "responses"):
            try:
                count = self.responses.count()
            except Exception:
                count = 0
            if count >= self.max_responses:
                return False
        return status_ok and time_ok

    def days_remaining(self) -> int | None:
        """
        Calculate days remaining until survey end date.

        Returns:
            Number of days remaining (can be negative if expired),
            or None if no end date is set.
        """
        if self.end_at is None:
            return None
        now = timezone.now()
        delta = self.end_at - now
        return delta.days

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    def set_key(self, key_bytes: bytes) -> None:
        digest, salt = make_key_hash(key_bytes)
        self.key_hash = digest
        self.key_salt = salt
        self.save(update_fields=["key_hash", "key_salt"])

    def set_dual_encryption(
        self, kek: bytes, password: str, recovery_phrase_words: list[str]
    ) -> None:
        """
        Set up Option 2 dual-path encryption for individual users.

        Args:
            kek: 32-byte survey encryption key (generated once)
            password: User's chosen password for unlocking
            recovery_phrase_words: List of BIP39 words for recovery

        This encrypts the KEK twice:
        1. With password-derived key -> encrypted_kek_password
        2. With recovery-phrase-derived key -> encrypted_kek_recovery

        Also stores a recovery hint (first...last word).
        """
        from .utils import create_recovery_hint, encrypt_kek_with_passphrase

        # Encrypt KEK with password
        self.encrypted_kek_password = encrypt_kek_with_passphrase(kek, password)

        # Encrypt KEK with recovery phrase
        recovery_phrase = " ".join(recovery_phrase_words)
        self.encrypted_kek_recovery = encrypt_kek_with_passphrase(kek, recovery_phrase)

        # Store recovery hint
        self.recovery_code_hint = create_recovery_hint(recovery_phrase_words)

        # Also set the old-style key hash for compatibility
        digest, salt = make_key_hash(kek)
        self.key_hash = digest
        self.key_salt = salt

        # Save all fields
        self.save(
            update_fields=[
                "encrypted_kek_password",
                "encrypted_kek_recovery",
                "recovery_code_hint",
                "key_hash",
                "key_salt",
            ]
        )

    def unlock_with_password(self, password: str) -> bytes | None:
        """
        Unlock survey using password (Option 2).

        Args:
            password: User's password

        Returns:
            32-byte KEK if successful, None if decryption fails

        This attempts to decrypt encrypted_kek_password with the provided password.
        """
        from cryptography.exceptions import InvalidTag

        from .utils import decrypt_kek_with_passphrase

        if not self.encrypted_kek_password:
            return None

        try:
            kek = decrypt_kek_with_passphrase(self.encrypted_kek_password, password)
            return kek
        except (InvalidTag, Exception):
            return None

    def unlock_with_recovery(self, recovery_phrase: str) -> bytes | None:
        """
        Unlock survey using recovery phrase (Option 2).

        Args:
            recovery_phrase: Space-separated BIP39 recovery phrase

        Returns:
            32-byte KEK if successful, None if decryption fails

        This attempts to decrypt encrypted_kek_recovery with the provided phrase.
        """
        from cryptography.exceptions import InvalidTag

        from .utils import decrypt_kek_with_passphrase

        if not self.encrypted_kek_recovery:
            return None

        try:
            kek = decrypt_kek_with_passphrase(
                self.encrypted_kek_recovery, recovery_phrase
            )
            return kek
        except (InvalidTag, Exception):
            return None

    def has_dual_encryption(self) -> bool:
        """Check if survey uses Option 2 dual-path encryption."""
        return bool(self.encrypted_kek_password and self.encrypted_kek_recovery)

    def has_any_encryption(self) -> bool:
        """
        Check if survey has any form of encryption enabled.

        Returns:
            True if the survey has at least one encryption method configured
            (password, recovery phrase, OIDC, or organization)

        This is used to determine if encryption setup is needed when publishing.
        A survey with any encryption method is considered "encrypted" and won't
        require the encryption setup flow.
        """
        return bool(
            self.encrypted_kek_password
            or self.encrypted_kek_recovery
            or self.encrypted_kek_oidc
            or self.encrypted_kek_org
        )

    def set_oidc_encryption(self, kek: bytes, user) -> None:
        """
        Set up OIDC encryption for automatic survey unlocking.

        Args:
            kek: 32-byte survey encryption key (same as dual encryption)
            user: User with associated UserOIDC record

        This encrypts the KEK with the user's OIDC-derived key,
        enabling automatic unlock when they're authenticated via SSO.
        """
        from .utils import encrypt_kek_with_oidc

        # Get user's OIDC record
        if not hasattr(user, "oidc"):
            raise ValueError(
                f"User {user.username} does not have OIDC authentication configured"
            )

        oidc_record = user.oidc

        # Encrypt KEK with OIDC-derived key
        salt = oidc_record.key_derivation_salt
        if isinstance(salt, memoryview):
            salt = salt.tobytes()
        elif not isinstance(salt, bytes):
            salt = bytes(salt)

        self.encrypted_kek_oidc = encrypt_kek_with_oidc(
            kek, oidc_record.provider, oidc_record.subject, salt
        )

        self.save(update_fields=["encrypted_kek_oidc"])

    def has_oidc_encryption(self) -> bool:
        """Check if survey has OIDC encryption enabled."""
        return bool(self.encrypted_kek_oidc)

    def unlock_with_oidc(self, user) -> bytes | None:
        """
        Unlock survey using OIDC authentication (automatic unlock).

        Args:
            user: User with OIDC authentication

        Returns:
            32-byte KEK if successful, None if decryption fails

        This attempts to decrypt encrypted_kek_oidc using the user's OIDC identity.
        """
        from cryptography.exceptions import InvalidTag

        from .utils import decrypt_kek_with_oidc

        if not self.encrypted_kek_oidc:
            return None

        # Check if user has OIDC authentication
        if not hasattr(user, "oidc"):
            return None

        oidc_record = user.oidc

        try:
            salt = oidc_record.key_derivation_salt
            if isinstance(salt, memoryview):
                salt = salt.tobytes()
            elif not isinstance(salt, bytes):
                salt = bytes(salt)

            kek = decrypt_kek_with_oidc(
                self.encrypted_kek_oidc, oidc_record.provider, oidc_record.subject, salt
            )
            return kek
        except (InvalidTag, Exception):
            return None

    def can_user_unlock_automatically(self, user) -> bool:
        """
        Check if user can automatically unlock this survey via OIDC.

        Args:
            user: User to check

        Returns:
            True if automatic unlock is possible, False otherwise
        """
        return (
            self.has_oidc_encryption()
            and hasattr(user, "oidc")
            and user.is_authenticated
        )

    def set_org_encryption(self, kek: bytes, organization: Organization) -> None:
        """
        Set up Option 1 organization-level key escrow.

        Args:
            kek: 32-byte survey encryption key (same KEK used for password/OIDC encryption)
            organization: Organization whose master key will encrypt the KEK

        This encrypts the KEK with the organization's master key,
        enabling organization owners/admins to recover surveys from their members.

        In production, organization.encrypted_master_key should be encrypted with
        AWS KMS or Azure Key Vault. For development/testing, it can be plaintext.
        """
        from .utils import encrypt_kek_with_org_key

        if not organization.encrypted_master_key:
            raise ValueError(
                f"Organization {organization.name} does not have a master key configured"
            )

        # Encrypt KEK with organization master key
        self.encrypted_kek_org = encrypt_kek_with_org_key(
            kek, organization.encrypted_master_key
        )

        self.save(update_fields=["encrypted_kek_org"])

    def has_org_encryption(self) -> bool:
        """Check if survey has organization-level encryption enabled."""
        return bool(self.encrypted_kek_org)

    def unlock_with_org_key(self, organization: Organization) -> bytes | None:
        """
        Unlock survey using organization master key (administrative recovery).

        Args:
            organization: Organization attempting to unlock the survey

        Returns:
            32-byte KEK if successful, None if decryption fails

        This should only be used by organization owners/admins for legitimate
        recovery scenarios. All calls should be logged for audit compliance.
        """
        from cryptography.exceptions import InvalidTag

        from .utils import decrypt_kek_with_org_key

        if not self.encrypted_kek_org:
            return None

        if not organization.encrypted_master_key:
            return None

        # Verify survey belongs to this organization
        if self.organization != organization:
            return None

        try:
            kek = decrypt_kek_with_org_key(
                self.encrypted_kek_org, organization.encrypted_master_key
            )
            return kek
        except (InvalidTag, Exception):
            return None

    # Data Governance Methods

    def close_survey(self, user: User) -> None:
        """Close survey and start retention period."""
        from datetime import timedelta

        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        self.closed_by = user
        self.deletion_date = self.closed_at + timedelta(days=self.retention_months * 30)
        self.save()

        # Schedule deletion warnings (will be implemented in tasks)
        # from .tasks import schedule_deletion_warnings
        # schedule_deletion_warnings.delay(self.id)

    def extend_retention(self, months: int, user: User, reason: str) -> None:
        """Extend retention period (max 24 months total)."""
        from datetime import timedelta

        if not self.closed_at:
            raise ValueError("Cannot extend retention on unclosed survey")

        # Check total retention doesn't exceed 24 months
        new_total_months = self.retention_months + months
        if new_total_months > 24:
            raise ValueError(
                f"Cannot exceed 24 months total retention "
                f"(currently at {self.retention_months} months, "
                f"trying to add {months} months)"
            )

        # Store old values for email notification
        old_retention_months = self.retention_months
        old_deletion_date = self.deletion_date

        # Update retention period and deletion date
        self.retention_months = new_total_months
        self.deletion_date = self.closed_at + timedelta(days=self.retention_months * 30)
        self.save()

        # Send email notification
        self._send_retention_extension_notification(
            user=user,
            old_months=old_retention_months,
            new_months=new_total_months,
            months_added=months,
            old_deletion_date=old_deletion_date,
            new_deletion_date=self.deletion_date,
            reason=reason,
        )

        # Log extension (will create DataRetentionExtension model later)
        # DataRetentionExtension.objects.create(...)

        # Reschedule warnings
        # from .tasks import schedule_deletion_warnings
        # schedule_deletion_warnings.delay(self.id)

    def soft_delete(self) -> None:
        """Soft delete survey (30-day grace period)."""
        from datetime import timedelta

        self.deleted_at = timezone.now()
        self.hard_deletion_date = self.deleted_at + timedelta(days=30)
        self.save()

        # Schedule hard deletion
        # from .tasks import schedule_hard_deletion
        # schedule_hard_deletion.apply_async(
        #     args=[self.id],
        #     eta=self.hard_deletion_date
        # )

    def hard_delete(self) -> None:
        """Permanently delete survey data."""
        # Delete responses
        if hasattr(self, "responses"):
            self.responses.all().delete()

        # Delete exports (will implement DataExport model later)
        # if hasattr(self, 'data_exports'):
        #     self.data_exports.all().delete()

        # Purge backups (external API call - to be implemented)
        # from .services import BackupService
        # BackupService.purge_survey_backups(self.id)

        # Keep audit trail summary (to be implemented)
        # AuditLog.objects.create(
        #     action='HARD_DELETE',
        #     survey_id=self.id,
        #     survey_name=self.name,
        #     timestamp=timezone.now()
        # )

        # Delete survey
        self.delete()

    @property
    def days_until_deletion(self) -> int | None:
        """Days remaining until automatic deletion."""
        if not self.deletion_date or self.deleted_at:
            return None
        delta = self.deletion_date - timezone.now()
        return max(0, delta.days)

    @property
    def can_extend_retention(self) -> bool:
        """Check if retention can be extended."""
        if not self.closed_at:
            return False
        return self.retention_months < 24

    def _send_retention_extension_notification(
        self,
        user: User,
        old_months: int,
        new_months: int,
        months_added: int,
        old_deletion_date,
        new_deletion_date,
        reason: str,
    ) -> None:
        """Send email notification when retention period is extended."""
        from django.conf import settings
        from django.template.loader import render_to_string

        from checktick_app.core.email_utils import (
            get_platform_branding,
            send_branded_email,
        )

        subject = f"Retention Period Extended: {self.name}"

        branding = get_platform_branding()

        # Send to survey owner
        markdown_content = render_to_string(
            "emails/data_governance/retention_extended.md",
            {
                "survey": self,
                "extended_by": user,
                "old_months": old_months,
                "new_months": new_months,
                "months_added": months_added,
                "old_deletion_date": old_deletion_date.strftime("%B %d, %Y"),
                "new_deletion_date": new_deletion_date.strftime("%B %d, %Y"),
                "reason": reason,
                "brand_title": branding["title"],
                "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            },
        )

        send_branded_email(
            to_email=self.owner.email,
            subject=subject,
            markdown_content=markdown_content,
            branding=branding,
        )

        # Also notify organization administrators
        if self.organization:
            org_admin_emails = [self.organization.owner.email]
            # Filter out survey owner if they're also org owner
            if self.owner.email not in org_admin_emails:
                for admin_email in org_admin_emails:
                    send_branded_email(
                        to_email=admin_email,
                        subject=subject,
                        markdown_content=markdown_content,
                        branding=branding,
                    )

    @property
    def is_closed(self) -> bool:
        """Check if survey is closed."""
        return self.status == self.Status.CLOSED or self.closed_at is not None


class SurveyQuestion(models.Model):
    class Types(models.TextChoices):
        TEXT = "text", "Free text"
        MULTIPLE_CHOICE_SINGLE = "mc_single", "Multiple choice (single)"
        MULTIPLE_CHOICE_MULTI = "mc_multi", "Multiple choice (multi)"
        LIKERT = "likert", "Likert scale"
        ORDERABLE = "orderable", "Orderable list"
        YESNO = "yesno", "Yes/No"
        DROPDOWN = "dropdown", "Dropdown"
        IMAGE_CHOICE = "image", "Image choice"
        TEMPLATE_PATIENT = "template_patient", "Patient details template"
        TEMPLATE_PROFESSIONAL = "template_professional", "Professional details template"

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="questions"
    )
    group = models.ForeignKey(
        QuestionGroup, on_delete=models.SET_NULL, null=True, blank=True
    )
    text = models.TextField()
    type = models.CharField(max_length=50, choices=Types.choices)
    options = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class SurveyQuestionCondition(models.Model):
    class Operator(models.TextChoices):
        EQUALS = "eq", "Equals"
        NOT_EQUALS = "neq", "Does not equal"
        CONTAINS = "contains", "Contains"
        NOT_CONTAINS = "not_contains", "Does not contain"
        GREATER_THAN = "gt", "Greater than"
        GREATER_EQUAL = "gte", "Greater or equal"
        LESS_THAN = "lt", "Less than"
        LESS_EQUAL = "lte", "Less or equal"
        EXISTS = "exists", "Answer provided"
        NOT_EXISTS = "not_exists", "Answer missing"

    class Action(models.TextChoices):
        JUMP_TO = "jump_to", "Jump to target"
        SHOW = "show", "Show target"
        SKIP = "skip", "Skip target"

    question = models.ForeignKey(
        SurveyQuestion, on_delete=models.CASCADE, related_name="conditions"
    )
    operator = models.CharField(
        max_length=16, choices=Operator.choices, default=Operator.EQUALS
    )
    value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Value to compare against the response when required by the operator.",
    )
    target_question = models.ForeignKey(
        "SurveyQuestion",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="incoming_conditions",
    )
    target_group = models.ForeignKey(
        QuestionGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="incoming_conditions",
    )
    action = models.CharField(
        max_length=32, choices=Action.choices, default=Action.JUMP_TO
    )
    order = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question", "order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(target_question__isnull=False, target_group__isnull=True)
                    | Q(target_question__isnull=True, target_group__isnull=False)
                ),
                name="surveyquestioncondition_single_target",
            )
        ]

    def clean(self):  # pragma: no cover - validated via tests
        super().clean()

        if bool(self.target_question) == bool(self.target_group):
            raise ValidationError(
                {
                    "target_question": "Specify exactly one of target_question or target_group.",
                    "target_group": "Specify exactly one of target_question or target_group.",
                }
            )

        if self.target_question and (
            self.target_question.survey_id != self.question.survey_id
        ):
            raise ValidationError(
                {
                    "target_question": "Target question must belong to the same survey as the triggering question.",
                }
            )

        if (
            self.target_group
            and not self.target_group.surveys.filter(
                id=self.question.survey_id
            ).exists()
        ):
            raise ValidationError(
                {
                    "target_group": "Target group must be attached to the same survey as the triggering question.",
                }
            )

        operators_requiring_value = {
            self.Operator.EQUALS,
            self.Operator.NOT_EQUALS,
            self.Operator.CONTAINS,
            self.Operator.NOT_CONTAINS,
            self.Operator.GREATER_THAN,
            self.Operator.GREATER_EQUAL,
            self.Operator.LESS_THAN,
            self.Operator.LESS_EQUAL,
        }
        if self.operator in operators_requiring_value and not self.value:
            raise ValidationError(
                {"value": "This operator requires a comparison value."}
            )


class SurveyMembership(models.Model):
    class Role(models.TextChoices):
        CREATOR = "creator", "Creator"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="survey_memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("survey", "user")


class SurveyResponse(models.Model):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="responses"
    )
    # Sensitive demographics encrypted per-survey
    enc_demographics = models.BinaryField(null=True, blank=True)
    # Non-sensitive answers stored normally
    answers = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="survey_responses",
    )
    # Optional link to an invite token to enforce one-response-per-token
    # Using OneToOne ensures the token can be consumed exactly once.
    access_token = models.OneToOneField(
        "SurveyAccessToken",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="response",
    )

    def store_demographics(self, survey_key: bytes, demographics: dict):
        self.enc_demographics = encrypt_sensitive(survey_key, demographics)

    def load_demographics(self, survey_key: bytes) -> dict:
        if not self.enc_demographics:
            return {}
        return decrypt_sensitive(survey_key, self.enc_demographics)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "submitted_by"],
                name="one_response_per_user_per_survey",
            )
        ]


class SurveyAccessToken(models.Model):
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="access_tokens"
    )
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_access_tokens"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="used_access_tokens",
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["survey", "expires_at"]),
        ]

    def is_valid(self) -> bool:  # pragma: no cover
        if self.used_at:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class SurveyProgress(models.Model):
    """
    Tracks partial survey progress for logged-in users and anonymous sessions.
    Allows users to resume incomplete surveys.
    """

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="progress_records"
    )

    # For authenticated users
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="survey_progress",
    )

    # For anonymous users (token/unlisted/public)
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)

    # Optional link to access token for token-based surveys
    access_token = models.ForeignKey(
        SurveyAccessToken,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress",
    )

    # Progress data
    partial_answers = models.JSONField(default=dict)
    current_question_id = models.IntegerField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    answered_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_question_answered_at = models.DateTimeField(null=True, blank=True)

    # Auto-cleanup: delete old progress after 30 days
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "user"],
                condition=Q(user__isnull=False),
                name="one_progress_per_user_per_survey",
            ),
            models.UniqueConstraint(
                fields=["survey", "session_key"],
                condition=Q(session_key__isnull=False),
                name="one_progress_per_session_per_survey",
            ),
        ]
        indexes = [
            models.Index(fields=["survey", "user"]),
            models.Index(fields=["survey", "session_key"]),
            models.Index(fields=["expires_at"]),
        ]

    def calculate_progress_percentage(self) -> int:
        """Calculate progress as percentage (0-100)"""
        if self.total_questions == 0:
            return 0
        return int((self.answered_count / self.total_questions) * 100)

    def update_progress(self, answers: dict, current_q_id: int | None = None):
        """Update progress with new answers"""
        self.partial_answers.update(answers)
        self.answered_count = len([v for v in self.partial_answers.values() if v])
        if current_q_id:
            self.current_question_id = current_q_id
        self.last_question_answered_at = timezone.now()
        self.save()


def validate_markdown_survey(md_text: str) -> list[dict]:
    if not md_text or not md_text.strip():
        raise ValidationError("Empty markdown")
    # Placeholder minimal validation
    return []


class AuditLog(models.Model):
    class Scope(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        SURVEY = "survey", "Survey"

    class Action(models.TextChoices):
        ADD = "add", "Add"
        REMOVE = "remove", "Remove"
        UPDATE = "update", "Update"
        KEY_RECOVERY = "key_recovery", "Key Recovery"

    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="audit_logs")
    scope = models.CharField(max_length=20, choices=Scope.choices)
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.CASCADE
    )
    survey = models.ForeignKey(Survey, null=True, blank=True, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=Action.choices)
    target_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="audit_targets"
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["scope", "organization", "survey"]),
            models.Index(fields=["created_at"]),
        ]


# -------------------- Collections (definitions) --------------------


class CollectionDefinition(models.Model):
    class Cardinality(models.TextChoices):
        ONE = "one", "One"
        MANY = "many", "Many"

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="collections"
    )
    key = models.SlugField(
        help_text="Stable key used in response JSON; unique per survey"
    )
    name = models.CharField(max_length=255)
    cardinality = models.CharField(
        max_length=10, choices=Cardinality.choices, default=Cardinality.MANY
    )
    min_count = models.PositiveIntegerField(default=0)
    max_count = models.PositiveIntegerField(null=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )

    class Meta:
        unique_together = ("survey", "key")
        indexes = [models.Index(fields=["survey", "parent"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.key})"

    def ancestors(self) -> list["CollectionDefinition"]:
        chain: list[CollectionDefinition] = []
        node = self.parent
        # Walk up the tree
        while node is not None:
            chain.append(node)
            node = node.parent
        return chain

    def clean(self):  # pragma: no cover - covered via tests
        from django.core.exceptions import ValidationError

        # Parent must be in the same survey
        if self.parent and self.parent.survey_id != self.survey_id:
            raise ValidationError(
                {"parent": "Parent collection must belong to the same survey."}
            )
        # Depth cap (2 levels: parent -> child). If parent has a parent, this would be level 3.
        if self.parent and self.parent.parent_id:
            raise ValidationError({"parent": "Maximum nesting depth is 2."})
        # Cardinality constraints
        if self.cardinality == self.Cardinality.ONE:
            if self.max_count is not None and self.max_count != 1:
                raise ValidationError(
                    {"max_count": "For cardinality 'one', max_count must be 1."}
                )
            if self.min_count not in (0, 1):
                raise ValidationError(
                    {"min_count": "For cardinality 'one', min_count must be 0 or 1."}
                )
        # min/max relationship
        if self.max_count is not None and self.min_count > self.max_count:
            raise ValidationError({"min_count": "min_count cannot exceed max_count."})
        # Cycle prevention: parent chain cannot include self
        for anc in self.ancestors():
            # If this instance already has a PK, ensure no ancestor is itself
            if self.pk and anc.pk == self.pk:
                raise ValidationError(
                    {"parent": "Collections cannot reference themselves (cycle)."}
                )


class CollectionItem(models.Model):
    class ItemType(models.TextChoices):
        GROUP = "group", "Group"
        COLLECTION = "collection", "Collection"

    collection = models.ForeignKey(
        CollectionDefinition, on_delete=models.CASCADE, related_name="items"
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    group = models.ForeignKey(
        QuestionGroup, null=True, blank=True, on_delete=models.CASCADE
    )
    child_collection = models.ForeignKey(
        CollectionDefinition,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="parent_links",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "order"],
                name="uq_collectionitem_order_per_collection",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        target = self.group or self.child_collection
        return f"{self.item_type}: {target}"

    def clean(self):  # pragma: no cover - covered via tests
        from django.core.exceptions import ValidationError

        # Exactly one of group or child_collection must be set
        if bool(self.group) == bool(self.child_collection):
            raise ValidationError(
                "Provide either a group or a child_collection, not both."
            )
        # item_type must match the provided field
        if self.item_type == self.ItemType.GROUP and not self.group:
            raise ValidationError({"group": "group must be set for item_type 'group'."})
        if self.item_type == self.ItemType.COLLECTION and not self.child_collection:
            raise ValidationError(
                {
                    "child_collection": "child_collection must be set for item_type 'collection'."
                }
            )
        # Group must belong to the same survey
        if self.group:
            survey_id = self.collection.survey_id
            if not self.group.surveys.filter(id=survey_id).exists():
                raise ValidationError(
                    {"group": "Selected group is not attached to this survey."}
                )
        # Child collection must be in same survey and be a direct child of this collection
        if self.child_collection:
            if self.child_collection.survey_id != self.collection.survey_id:
                raise ValidationError(
                    {
                        "child_collection": "Child collection must belong to the same survey."
                    }
                )
            if self.child_collection.parent_id != self.collection_id:
                raise ValidationError(
                    {
                        "child_collection": "Child collection's parent must be this collection."
                    }
                )


# ============================================================================
# Data Governance Models
# ============================================================================


class DataExport(models.Model):
    """
    Tracks data exports for audit trail and download management.

    - UUID primary key for secure, non-sequential export identification
    - Download tokens prevent unauthorized access after export creation
    - Audit trail tracks who exported what and when
    - Downloaded_at tracks actual downloads for compliance reporting
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="exports")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="exports"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Download management
    download_token = models.CharField(max_length=64, unique=True, db_index=True)
    download_url_expires_at = models.DateTimeField()
    downloaded_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)

    # Export metadata
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    response_count = models.PositiveIntegerField()
    export_format = models.CharField(max_length=10, default="csv")  # Future: json, xlsx

    # Encryption (stored exports are encrypted at rest)
    is_encrypted = models.BooleanField(default=True)
    encryption_key_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["survey", "-created_at"]),
            models.Index(fields=["download_token"]),
        ]

    def __str__(self) -> str:
        return f"Export {self.id} for {self.survey.title} ({self.created_at})"

    @property
    def is_download_url_expired(self) -> bool:
        """Check if the download URL has expired."""
        from django.utils import timezone

        return timezone.now() > self.download_url_expires_at

    def mark_downloaded(self) -> None:
        """Record that this export was downloaded."""
        from django.utils import timezone

        if not self.downloaded_at:
            self.downloaded_at = timezone.now()
        self.download_count += 1
        self.save(update_fields=["downloaded_at", "download_count"])


class LegalHold(models.Model):
    """
    Legal hold prevents automatic deletion of survey data.

    - OneToOne with Survey - one hold per survey
    - Blocks all automatic deletion processes
    - Requires reason and authority for audit compliance
    - Can only be placed/removed by org owners
    """

    survey = models.OneToOneField(
        Survey, on_delete=models.CASCADE, related_name="legal_hold"
    )
    placed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="legal_holds_placed"
    )
    placed_at = models.DateTimeField(auto_now_add=True)

    reason = models.TextField()
    authority = models.CharField(max_length=255)  # e.g., "Court order XYZ-2024-001"

    removed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legal_holds_removed",
    )
    removed_at = models.DateTimeField(null=True, blank=True)
    removal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-placed_at"]

    def __str__(self) -> str:
        status = "Active" if not self.removed_at else "Removed"
        return f"Legal Hold ({status}) on {self.survey.title}"

    @property
    def is_active(self) -> bool:
        """Check if this legal hold is currently active."""
        return self.removed_at is None

    def remove(self, user: User, reason: str) -> None:
        """Remove the legal hold."""
        from django.utils import timezone

        # Store values before updating for email notification
        hold_placed_date = self.placed_at
        hold_duration = timezone.now() - self.placed_at

        self.removed_by = user
        self.removed_at = timezone.now()
        self.removal_reason = reason
        self.save(update_fields=["removed_by", "removed_at", "removal_reason"])

        # Send email notification
        self._send_legal_hold_removed_notification(
            user=user,
            reason=reason,
            hold_placed_date=hold_placed_date,
            hold_duration=hold_duration,
        )

    def _send_legal_hold_removed_notification(
        self, user: User, reason: str, hold_placed_date, hold_duration
    ) -> None:
        """Send email notification when legal hold is removed."""
        from django.conf import settings
        from django.template.loader import render_to_string

        from checktick_app.core.email_utils import (
            get_platform_branding,
            send_branded_email,
        )

        subject = f"Legal Hold Removed: {self.survey.name}"

        branding = get_platform_branding()

        # Calculate hold duration in days
        days_duration = hold_duration.days

        # Format new deletion date if survey is closed
        new_deletion_date = None
        if self.survey.deletion_date:
            new_deletion_date = self.survey.deletion_date.strftime("%B %d, %Y")

        markdown_content = render_to_string(
            "emails/data_governance/legal_hold_removed.md",
            {
                "survey": self.survey,
                "removed_by": user,
                "removed_date": self.removed_at.strftime("%B %d, %Y at %I:%M %p"),
                "hold_placed_date": hold_placed_date.strftime("%B %d, %Y"),
                "hold_duration": f"{days_duration} days",
                "reason": reason,
                "new_deletion_date": new_deletion_date,
                "brand_title": branding["title"],
                "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            },
        )

        # Send to survey owner
        send_branded_email(
            to_email=self.survey.owner.email,
            subject=subject,
            markdown_content=markdown_content,
            branding=branding,
        )

        # Send to organization owner if exists
        if self.survey.organization:
            if self.survey.organization.owner.email != self.survey.owner.email:
                send_branded_email(
                    to_email=self.survey.organization.owner.email,
                    subject=subject,
                    markdown_content=markdown_content,
                    branding=branding,
                )


class DataCustodian(models.Model):
    """
    Grant download-only access to specific surveys for external auditors.

    - User has download access without organization membership
    - Access can be time-limited (expires_at)
    - No edit permissions - read/export only
    - Audit trail of who granted access and why
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="custodian_assignments"
    )
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="data_custodians"
    )

    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="custodian_grants",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    reason = models.TextField()  # Why this user needs access

    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_revocations",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "survey"],
                condition=models.Q(revoked_at__isnull=True),
                name="uq_active_custodian_per_user_survey",
            ),
        ]

    def __str__(self) -> str:
        status = "Active" if self.is_active else "Revoked"
        return f"Data Custodian ({status}): {self.user.email} on {self.survey.title}"

    @property
    def is_active(self) -> bool:
        """Check if this custodian assignment is currently active."""
        from django.utils import timezone

        if self.revoked_at:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def revoke(self, user: User) -> None:
        """Revoke custodian access."""
        from django.utils import timezone

        self.revoked_by = user
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_by", "revoked_at"])


class DataRetentionExtension(models.Model):
    """
    Audit trail for retention period extensions.

    - Immutable log of each extension request
    - Tracks who requested, when, and why
    - Shows progression of retention period over time
    - Critical for compliance audits
    """

    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="retention_extensions"
    )
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="retention_extensions"
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    # Extension details
    previous_deletion_date = models.DateTimeField()
    new_deletion_date = models.DateTimeField()
    months_extended = models.PositiveIntegerField()

    # Justification for audit trail
    reason = models.TextField()

    # Approval workflow (future: require org owner approval)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retention_extension_approvals",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["survey", "-requested_at"]),
        ]

    def __str__(self) -> str:
        return f"Retention extension for {self.survey.title} (+{self.months_extended} months)"

    @property
    def is_approved(self) -> bool:
        """Check if this extension has been approved."""
        return self.approved_at is not None

    @property
    def days_extended(self) -> int:
        """Calculate the number of days extended."""
        delta = self.new_deletion_date - self.previous_deletion_date
        return delta.days
