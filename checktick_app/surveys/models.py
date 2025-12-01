from __future__ import annotations

import json
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


# Supported languages for survey translation
# Based on available locale directories
SUPPORTED_SURVEY_LANGUAGES = [
    ("en", "English"),
    ("ar", "العربية (Arabic)"),
    ("cy", "Cymraeg (Welsh)"),
    ("de", "Deutsch (German)"),
    ("es", "Español (Spanish)"),
    ("fr", "Français (French)"),
    ("hi", "हिन्दी (Hindi)"),
    ("it", "Italiano (Italian)"),
    ("pl", "Polski (Polish)"),
    ("pt", "Português (Portuguese)"),
    ("ur", "اردو (Urdu)"),
    ("zh_Hans", "简体中文 (Simplified Chinese)"),
]

# Map language codes to their native names
LANGUAGE_NAMES = {code: name for code, name in SUPPORTED_SURVEY_LANGUAGES}

# Map language codes to emoji flags
LANGUAGE_FLAGS = {
    "en": "🇬🇧",
    "ar": "🇸🇦",
    "cy": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "de": "🇩🇪",
    "es": "🇪🇸",
    "fr": "🇫🇷",
    "hi": "🇮🇳",
    "it": "🇮🇹",
    "pl": "🇵🇱",
    "pt": "🇵🇹",
    "ur": "🇵🇰",
    "zh_Hans": "🇨🇳",
}


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


class Team(models.Model):
    """
    A collaboration team for groups of users with shared billing.

    Teams can be standalone (own billing) or hosted within an Organisation
    (organisation manages billing). Teams provide collaboration features
    without the full governance capabilities of Organisations.
    """

    class Size(models.TextChoices):
        SMALL = "small", "Small (5 users)"
        MEDIUM = "medium", "Medium (10 users)"
        LARGE = "large", "Large (20 users)"
        CUSTOM = "custom", "Custom (>20 users)"

    name = models.CharField(max_length=255)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="owned_teams"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
        help_text="Optional parent organisation (for org-hosted teams)",
    )

    size = models.CharField(
        max_length=20,
        choices=Size.choices,
        default=Size.SMALL,
        help_text="Team size tier determining member limit and pricing",
    )
    custom_max_members = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum members for custom-sized teams (>20 users)",
    )
    max_surveys = models.PositiveIntegerField(
        default=50, help_text="Maximum number of surveys this team can create"
    )

    # Generic billing reference (not tied to specific payment provider)
    subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External subscription reference (payment provider agnostic)",
    )

    # Encryption (placeholder for Phase 2 - Vault integration)
    encrypted_master_key = models.BinaryField(
        blank=True,
        null=True,
        editable=False,
        help_text="Team master key for administrative recovery (will be encrypted with Vault in Phase 2)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    @property
    def max_members(self) -> int:
        """Get maximum member count based on size tier."""
        if self.size == self.Size.CUSTOM:
            return self.custom_max_members or 20
        return {
            self.Size.SMALL: 5,
            self.Size.MEDIUM: 10,
            self.Size.LARGE: 20,
        }.get(self.size, 5)

    def current_member_count(self) -> int:
        """Get current number of team members."""
        return self.memberships.count()

    def can_add_members(self) -> bool:
        """Check if team has capacity for more members."""
        return self.current_member_count() < self.max_members

    def current_survey_count(self) -> int:
        """Get current number of surveys owned by this team."""
        return self.surveys.count()

    def can_create_surveys(self) -> bool:
        """Check if team has capacity for more surveys."""
        return self.current_survey_count() < self.max_surveys


class TeamMembership(models.Model):
    """
    Membership linking users to teams with specific roles.

    Roles are team-level and persist if the team migrates to an Organisation.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CREATOR = "creator", "Creator"
        VIEWER = "viewer", "Viewer"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="team_memberships"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CREATOR,
        help_text="Role persists if team migrates to organisation",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username} - {self.team.name} ({self.role})"


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
    imported_from = models.ForeignKey(
        "PublishedQuestionGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_copies",
        help_text="Source published template if this was imported",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    def to_markdown(self, survey=None) -> str:
        """Export this group to markdown format."""
        # Import here to avoid circular dependency

        # Create a temporary survey-like structure for export
        # Implementation will be completed in views module
        raise NotImplementedError("Will be implemented with export functionality")

    def can_publish(self, user: User, level: str) -> bool:
        """Check if user can publish this group at given level."""
        from .permissions import can_publish_question_group

        return can_publish_question_group(user, self, level)


class PublishedQuestionGroup(models.Model):
    """A published, reusable QuestionGroup template."""

    class PublicationLevel(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        GLOBAL = "global", "Global"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DELETED = "deleted", "Deleted (Soft Delete)"

    # Source
    source_group = models.ForeignKey(
        QuestionGroup,
        on_delete=models.SET_NULL,
        null=True,
        related_name="published_versions",
        help_text="Original QuestionGroup this was published from",
    )

    # Ownership & Permissions
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="published_templates"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Organization for org-level publications",
    )
    publication_level = models.CharField(
        max_length=20, choices=PublicationLevel.choices
    )

    # Content (snapshot at publication time)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    markdown = models.TextField(help_text="Markdown representation")

    # Attribution
    attribution = models.JSONField(
        default=dict,
        blank=True,
        help_text="Attribution metadata (authors, citation, PMID, DOI, license)",
    )
    show_publisher_credit = models.BooleanField(
        default=True,
        help_text="Whether to show publisher name/organization in public listings",
    )

    # Metadata
    tags = models.JSONField(
        default=list, blank=True, help_text="Tags for categorization and search"
    )
    language = models.CharField(max_length=10, default="en")
    version = models.CharField(max_length=50, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )

    # Usage tracking
    import_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["publication_level", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-import_count"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(publication_level="organization", organization__isnull=False)
                    | Q(publication_level="global")
                ),
                name="org_required_for_org_level",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        level = (
            "Global"
            if self.publication_level == "global"
            else f"Org: {self.organization}"
        )
        return f"{self.name} ({level})"

    def increment_import_count(self) -> None:
        """Increment the import counter when template is used."""
        self.import_count += 1
        self.save(update_fields=["import_count"])


class Survey(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="surveys")
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="surveys",
        help_text="Team this survey belongs to (if any)",
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
    allow_any_authenticated = models.BooleanField(
        default=False,
        help_text="Allow any authenticated user to access this survey (not just invited users)",
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
    # Whether SSO users must set a passphrase for patient data surveys
    # When True + survey has patient data: SSO users cannot use auto-unlock alone
    require_passphrase_for_patient_data = models.BooleanField(
        default=True,
        help_text="Require SSO users to set a passphrase when survey collects patient data (recommended)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Language and Translation fields
    language = models.CharField(
        max_length=10,
        default="en",
        help_text="Primary language code (ISO 639-1, e.g., 'en', 'fr', 'es')",
    )
    translation_group = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="UUID linking translated versions of the same survey",
    )
    is_original = models.BooleanField(
        default=True,
        help_text="True if this is the original survey, False if it's a translation",
    )
    translated_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="translations",
        help_text="Reference to the survey this was translated from",
    )

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

    def collects_patient_data(self) -> bool:
        """
        Check if this survey collects patient data.

        Returns:
            True if survey has a patient_details_encrypted question group

        A survey collects patient data if it includes a question group with
        schema.template == "patient_details_encrypted". Such surveys require
        whole-response encryption (not just demographics).
        """
        return self.question_groups.filter(
            schema__template="patient_details_encrypted"
        ).exists()

    def requires_whole_response_encryption(self) -> bool:
        """
        Check if responses to this survey should be fully encrypted.

        Returns:
            True if all response data (not just demographics) should be encrypted

        Surveys collecting patient data require the entire response to be
        encrypted with store_complete_response(), not just demographics.
        """
        return self.collects_patient_data()

    def sso_user_needs_passphrase(self) -> bool:
        """
        Check if SSO users need to set a passphrase for this survey.

        Returns:
            True if SSO users must set passphrase (not just use auto-unlock)

        When survey collects patient data AND require_passphrase_for_patient_data
        is True, SSO users must set up password-based encryption in addition to
        (or instead of) OIDC auto-unlock.
        """
        return self.collects_patient_data() and self.require_passphrase_for_patient_data

    def is_patient_data_readonly(self) -> bool:
        """
        Check if this survey's patient data is in readonly mode due to tier downgrade.

        Returns:
            True if survey collects patient data but owner no longer has permission.

        This happens when a user:
        1. Had a paid tier (Pro, Team, Organization)
        2. Created a survey with patient data
        3. Downgraded to FREE tier

        In this state:
        - Survey data remains encrypted and accessible
        - Survey cannot be edited (questions/groups are readonly)
        - Survey responses can still be viewed (with unlock)
        - User must upgrade to edit the survey again
        """
        if not self.collects_patient_data():
            return False

        from checktick_app.core.tier_limits import check_patient_data_permission

        can_collect, _ = check_patient_data_permission(self.owner)
        return not can_collect

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

    # Translation and Cloning Methods

    def get_available_translations(self):
        """
        Get all translations of this survey.

        Returns:
            QuerySet of Survey objects that are translations of this survey,
            excluding this survey itself.
        """
        if not self.translation_group:
            return Survey.objects.none()
        return Survey.objects.filter(translation_group=self.translation_group).exclude(
            id=self.id
        )

    def get_translation(self, language_code: str):
        """
        Get a specific translation by language code.

        Args:
            language_code: Language code (e.g., 'fr', 'es', 'de')

        Returns:
            Survey object if translation exists, None otherwise
        """
        if not self.translation_group:
            return None
        return (
            Survey.objects.filter(
                translation_group=self.translation_group, language=language_code
            )
            .exclude(id=self.id)
            .first()
        )

    def create_clone(
        self, new_name: str | None = None, new_slug: str | None = None
    ) -> "Survey":
        """
        Create a complete clone of this survey.

        This creates a new survey with:
        - All question groups (as copies, not references)
        - All questions with their conditions
        - Same settings and configuration
        - New name and slug

        Args:
            new_name: Name for the cloned survey (defaults to "Copy of [original]")
            new_slug: Slug for the cloned survey (auto-generated if not provided)

        Returns:
            New Survey object (unsaved, in DRAFT status)
        """
        from django.utils.text import slugify as django_slugify

        # Generate name and slug
        if new_name is None:
            new_name = f"Copy of {self.name}"
        if new_slug is None:
            base_slug = django_slugify(new_name)
            new_slug = base_slug
            counter = 1
            while Survey.objects.filter(slug=new_slug).exists():
                new_slug = f"{base_slug}-{counter}"
                counter += 1

        # Create new survey with same settings
        cloned_survey = Survey(
            owner=self.owner,
            organization=self.organization,
            name=new_name,
            slug=new_slug,
            description=self.description,
            style=self.style.copy() if self.style else {},
            # Reset dates and publishing status
            status=Survey.Status.DRAFT,
            visibility=self.visibility,
            start_at=None,
            end_at=None,
            published_at=None,
            unlisted_key=None,
            max_responses=self.max_responses,
            captcha_required=self.captcha_required,
            no_patient_data_ack=self.no_patient_data_ack,
            allow_any_authenticated=self.allow_any_authenticated,
            # Copy encryption settings (but not the actual keys - those are survey-specific)
            recovery_threshold=self.recovery_threshold,
            recovery_shares_count=self.recovery_shares_count,
            # Copy retention settings
            retention_months=self.retention_months,
            # Language settings - same language as original
            language=self.language,
            is_original=True,
            # No translation linking for plain clones
            translation_group=None,
            translated_from=None,
        )
        cloned_survey.save()

        # Clone question groups and questions
        for qg in self.question_groups.all():
            # Create a copy of the question group
            cloned_qg = QuestionGroup.objects.create(
                owner=qg.owner,
                name=qg.name,
                description=qg.description,
            )

            # Copy all questions from this group
            questions_map = {}  # Maps old question ID to new question
            for question in self.questions.filter(group=qg):
                cloned_question = SurveyQuestion.objects.create(
                    survey=cloned_survey,
                    group=cloned_qg,
                    text=question.text,
                    type=question.type,
                    required=question.required,
                    order=question.order,
                    options=question.options.copy() if question.options else {},
                    dataset=question.dataset,
                )
                questions_map[question.id] = cloned_question

            # Copy question conditions (after all questions are created)
            for question in self.questions.filter(group=qg):
                for condition in question.conditions.all():
                    # Map old question IDs to new ones for target_question
                    target = None
                    if (
                        condition.target_question_id
                        and condition.target_question_id in questions_map
                    ):
                        target = questions_map[condition.target_question_id]

                    SurveyQuestionCondition.objects.create(
                        question=questions_map[question.id],
                        operator=condition.operator,
                        value=condition.value,
                        target_question=target,
                        action=condition.action,
                        order=condition.order,
                        description=condition.description,
                    )

            # Add question group to survey
            cloned_survey.question_groups.add(cloned_qg)

        return cloned_survey

    def create_translation(
        self, target_language: str, translator_name: str | None = None
    ) -> "Survey":
        """
        Create a translation clone of this survey.

        This creates a clone and sets up translation linking:
        - Creates or reuses a translation_group UUID
        - Sets the target language
        - Marks as translated (is_original=False)
        - Links back to source survey

        Note: This only creates the structure. The actual translation
        of question text is done separately (typically via LLM).

        Args:
            target_language: Target language code (e.g., 'fr', 'es', 'de')
            translator_name: Optional name/identifier for translator

        Returns:
            New Survey object (saved, in DRAFT status, ready for translation)

        Raises:
            ValueError: If translation already exists for this language
        """
        import uuid

        # Check if translation already exists
        if self.translation_group:
            existing = self.get_translation(target_language)
            if existing:
                raise ValueError(
                    f"Translation to {target_language} already exists (ID: {existing.id})"
                )

        # Ensure original has a translation group
        if not self.translation_group:
            self.translation_group = str(uuid.uuid4())
            self.save(update_fields=["translation_group"])

        # Create the clone
        translated_name = f"{self.name} ({target_language.upper()})"
        cloned_survey = self.create_clone(
            new_name=translated_name, new_slug=f"{self.slug}-{target_language}"
        )

        # Update translation-specific fields
        cloned_survey.language = target_language
        cloned_survey.translation_group = self.translation_group
        cloned_survey.is_original = False
        cloned_survey.translated_from = self
        cloned_survey.save(
            update_fields=[
                "language",
                "translation_group",
                "is_original",
                "translated_from",
            ]
        )

        return cloned_survey

    def translate_survey_content(
        self, target_survey: "Survey", use_llm: bool = True
    ) -> dict[str, any]:
        """
        Translate the text content of this survey into the target survey.

        This method translates:
        - Survey name and description
        - Question text and options
        - Question group names and descriptions

        Args:
            target_survey: The survey to populate with translated content
            use_llm: Whether to use LLM for translation (default: True)

        Returns:
            Dictionary with translation results:
            {
                'success': bool,
                'translated_fields': int,
                'errors': list,
                'warnings': list
            }

        Note: Target survey must already exist (created via create_translation).
        This method updates the target survey in place.
        """
        from .llm_client import (
            ConversationalSurveyLLM,
            load_translation_prompt_from_docs,
        )

        results = {
            "success": False,
            "translated_fields": 0,
            "errors": [],
            "warnings": [],
        }

        # Verify target is a translation
        if target_survey.translated_from_id != self.id:
            results["errors"].append(
                "Target survey is not a translation of this survey"
            )
            return results

        target_lang = target_survey.language
        target_lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)

        if not use_llm:
            results["warnings"].append(
                "LLM translation disabled - content must be translated manually"
            )
            return results

        try:
            llm = ConversationalSurveyLLM()
        except Exception as e:
            results["errors"].append(f"Failed to initialize LLM: {str(e)}")
            return results

        # Build complete survey structure for context-aware translation
        try:
            # Collect all content to translate
            survey_structure = {
                "metadata": {
                    "name": self.name or "",
                    "description": self.description or "",
                },
                "question_groups": [],
            }

            # Gather all question groups and questions
            for source_qg in self.question_groups.all():
                group_data = {
                    "name": source_qg.name or "",
                    "description": source_qg.description or "",
                    "questions": [],
                }

                source_questions = self.questions.filter(group=source_qg).order_by(
                    "order"
                )
                for source_q in source_questions:
                    question_data = {"text": source_q.text or ""}

                    # Include choices if present
                    if source_q.options and isinstance(source_q.options, dict):
                        if "choices" in source_q.options:
                            question_data["choices"] = source_q.options["choices"]

                    # Include likert scale labels
                    if source_q.type == "likert" and source_q.options:
                        if isinstance(source_q.options, list) and source_q.options:
                            # Check if it's categories (list of labels) or number scale (dict)
                            first_option = source_q.options[0]
                            if isinstance(first_option, dict):
                                # Number scale format with min/max/left/right labels
                                if first_option.get("type") in [
                                    "number-scale",
                                    "number",
                                ]:
                                    scale_data = {}
                                    if "left" in first_option and first_option["left"]:
                                        scale_data["left_label"] = first_option["left"]
                                    if (
                                        "right" in first_option
                                        and first_option["right"]
                                    ):
                                        scale_data["right_label"] = first_option[
                                            "right"
                                        ]
                                    if scale_data:
                                        question_data["likert_scale"] = scale_data
                                # Categories format with labels list
                                elif "labels" in first_option:
                                    question_data["likert_categories"] = first_option[
                                        "labels"
                                    ]
                            elif isinstance(first_option, str):
                                # Simple list of category strings
                                question_data["likert_categories"] = source_q.options
                        elif isinstance(source_q.options, list):
                            # List of strings (categories)
                            question_data["likert_categories"] = source_q.options

                    group_data["questions"].append(question_data)

                survey_structure["question_groups"].append(group_data)

            # Load system prompt from documentation for transparency
            # Template variables are substituted automatically
            system_msg = load_translation_prompt_from_docs(
                target_language_name=target_lang_name, target_language_code=target_lang
            )

            # Send entire survey for translation
            conversation = [
                {
                    "role": "user",
                    "content": f"""Translate this complete medical survey to {target_lang_name}.

SURVEY TO TRANSLATE:
{json.dumps(survey_structure, ensure_ascii=False, indent=2)}

Return the translation as JSON following the exact structure specified in the system message.""",
                }
            ]

            response = llm.chat_with_custom_system_prompt(
                system_prompt=system_msg,
                conversation_history=conversation,
                temperature=0.2,  # Lower temperature for more consistent medical translations
                max_tokens=8000,  # Higher limit for complete survey translations
            )

            if not response:
                results["errors"].append("No response from translation service")
                return results

            # Log the raw response for debugging
            import logging
            import re

            logger = logging.getLogger(__name__)
            logger.info(
                f"LLM response length: {len(response) if response else 0} chars"
            )
            logger.debug(
                f"LLM response (first 500 chars): {response[:500] if response else 'None'}"
            )

            # Extract JSON from response (LLM may wrap it in markdown or add explanatory text)
            json_text = response

            # Try to extract JSON from markdown code blocks
            json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
                logger.info("Extracted JSON from markdown code block")
            else:
                # Try to find JSON object boundaries
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                    logger.info("Extracted JSON by finding object boundaries")

            # Parse the complete translation
            try:
                translation = json.loads(json_text)
            except json.JSONDecodeError as e:
                # Log the problematic JSON for debugging
                logger.error(f"JSON decode error at position {e.pos}: {str(e)}")
                logger.error(
                    f"Context around error (chars {max(0, e.pos-100)}:{e.pos+100}): {json_text[max(0, e.pos-100):e.pos+100]}"
                )

                # Try to salvage the JSON by fixing common issues
                try:
                    import re

                    fixed_json = json_text

                    # Remove trailing commas before closing braces/brackets (multiple passes)
                    prev_json = None
                    while prev_json != fixed_json:
                        prev_json = fixed_json
                        fixed_json = re.sub(r",(\s*[}\]])", r"\1", fixed_json)

                    # Remove any comments (// or /* */)
                    fixed_json = re.sub(r"//.*?$", "", fixed_json, flags=re.MULTILINE)
                    fixed_json = re.sub(r"/\*.*?\*/", "", fixed_json, flags=re.DOTALL)

                    translation = json.loads(fixed_json)
                    logger.info("Successfully parsed JSON after automatic fixes")
                except Exception as fix_error:
                    logger.error(f"Failed to fix JSON: {str(fix_error)}")
                    logger.error(f"Full response for debugging:\n{response}")
                    results["errors"].append(
                        f"Failed to parse translation response: {str(e)}"
                    )
                    return results

            # Check confidence level
            confidence = translation.get("confidence", "low")
            if confidence == "low":
                results["warnings"].append(
                    f"⚠️ LOW CONFIDENCE: {translation.get('confidence_notes', 'Professional medical translator review recommended')}"
                )
            elif confidence == "medium":
                results["warnings"].append(
                    f"MEDIUM CONFIDENCE: {translation.get('confidence_notes', 'Some terms may need review')}"
                )

            # Apply translations to target survey
            # Translate metadata
            metadata = translation.get("metadata", {})
            if metadata.get("name"):
                target_survey.name = metadata["name"]
                results["translated_fields"] += 1
            if metadata.get("description"):
                target_survey.description = metadata["description"]
                results["translated_fields"] += 1

            target_survey.save(update_fields=["name", "description"])

            # Translate question groups and questions
            translated_groups = translation.get("question_groups", [])
            source_groups = list(self.question_groups.all())

            for source_qg, trans_group in zip(source_groups, translated_groups):
                # Find corresponding group in target survey
                target_qg = target_survey.question_groups.filter(
                    name=source_qg.name
                ).first()
                if not target_qg:
                    continue

                # Apply group translations
                if trans_group.get("name"):
                    target_qg.name = trans_group["name"]
                    results["translated_fields"] += 1
                if trans_group.get("description"):
                    target_qg.description = trans_group["description"]
                    results["translated_fields"] += 1

                target_qg.save(update_fields=["name", "description"])

                # Translate questions
                source_questions = list(
                    self.questions.filter(group=source_qg).order_by("order")
                )
                target_questions = list(
                    target_survey.questions.filter(group=target_qg).order_by("order")
                )
                trans_questions = trans_group.get("questions", [])

                for source_q, target_q, trans_q in zip(
                    source_questions, target_questions, trans_questions
                ):
                    if trans_q.get("text"):
                        target_q.text = trans_q["text"]
                        results["translated_fields"] += 1

                    # Apply translated choices if present
                    if trans_q.get("choices"):
                        if target_q.options and isinstance(target_q.options, dict):
                            target_q.options = {
                                **target_q.options,
                                "choices": trans_q["choices"],
                            }
                            results["translated_fields"] += 1

                    # Apply translated likert categories if present
                    if trans_q.get("likert_categories"):
                        if isinstance(target_q.options, list):
                            # Simple list format
                            target_q.options = trans_q["likert_categories"]
                            results["translated_fields"] += 1
                        elif isinstance(target_q.options, list) and target_q.options:
                            first_opt = target_q.options[0]
                            if isinstance(first_opt, dict) and "labels" in first_opt:
                                # Categories format with labels dict
                                first_opt["labels"] = trans_q["likert_categories"]
                                results["translated_fields"] += 1

                    # Apply translated likert number scale labels if present
                    if trans_q.get("likert_scale"):
                        scale_data = trans_q["likert_scale"]
                        if isinstance(target_q.options, list) and target_q.options:
                            first_opt = target_q.options[0]
                            if isinstance(first_opt, dict):
                                if "left_label" in scale_data:
                                    first_opt["left"] = scale_data["left_label"]
                                    results["translated_fields"] += 1
                                if "right_label" in scale_data:
                                    first_opt["right"] = scale_data["right_label"]
                                    results["translated_fields"] += 1

                    target_q.save(update_fields=["text", "options"])

        except Exception as e:
            results["errors"].append(f"Error during translation: {str(e)}")

        # Set success flag
        results["success"] = (
            len(results["errors"]) == 0 and results["translated_fields"] > 0
        )

        if results["success"]:
            results["warnings"].append(
                "Please review translations for accuracy before publishing"
            )

        return results

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
    dataset = models.ForeignKey(
        "DataSet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
        help_text="Optional link to a shared dataset for dropdown options",
    )

    class Meta:
        ordering = ["order", "id"]


def question_image_upload_path(instance, filename):
    """
    Generate upload path for question images.
    Images are stored in: question_images/{survey_slug}/{question_id}/{filename}
    """
    import os

    ext = os.path.splitext(filename)[1].lower()
    # Use a UUID for the filename to avoid conflicts
    import uuid

    new_filename = f"{uuid.uuid4().hex}{ext}"
    return f"question_images/{instance.question.survey.slug}/{instance.question.id}/{new_filename}"


class QuestionImage(models.Model):
    """
    Stores images for image choice questions.

    WARNING: Images are NOT encrypted and should only be used for
    non-medical, non-patient-identifying content.
    """

    question = models.ForeignKey(
        SurveyQuestion, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=question_image_upload_path)
    label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional label/alt text for the image",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image {self.order} for question {self.question_id}"

    @property
    def url(self):
        """Return the URL for the image."""
        if self.image:
            return self.image.url
        return None


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
        SHOW = "show", "Show when condition met (hidden by default)"
        JUMP_TO = "jump_to", "Skip ahead to question"
        SKIP = "skip", "Hide when condition met"
        END_SURVEY = "end_survey", "End survey"

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
                    Q(target_question__isnull=False)
                    | Q(action="end_survey", target_question__isnull=True)
                ),
                name="surveyquestioncondition_single_target",
            )
        ]

    def clean(self):  # pragma: no cover - validated via tests
        super().clean()

        # END_SURVEY doesn't require a target
        if self.action == self.Action.END_SURVEY:
            return

        if not self.target_question:
            raise ValidationError(
                {
                    "target_question": "Target question is required (unless action is END_SURVEY).",
                }
            )

        if self.target_question.survey_id != self.question.survey_id:
            raise ValidationError(
                {
                    "target_question": "Target question must belong to the same survey as the triggering question.",
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
    # Sensitive demographics encrypted per-survey (legacy - kept for backwards compatibility)
    enc_demographics = models.BinaryField(null=True, blank=True)
    # Non-sensitive answers stored normally (when survey is not encrypted)
    answers = models.JSONField(default=dict)
    # Encrypted answers (when survey has patient data or user chooses encryption)
    enc_answers = models.BinaryField(
        null=True,
        blank=True,
        help_text="Encrypted survey answers (AES-256-GCM) for patient data surveys",
    )
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

    def _to_bytes(self, data) -> bytes:
        """Convert memoryview or bytes to bytes."""
        if isinstance(data, memoryview):
            return data.tobytes()
        if isinstance(data, bytes):
            return data
        return bytes(data)

    def store_demographics(self, survey_key: bytes, demographics: dict):
        self.enc_demographics = encrypt_sensitive(survey_key, demographics)

    def load_demographics(self, survey_key: bytes) -> dict:
        if not self.enc_demographics:
            return {}
        return decrypt_sensitive(survey_key, self._to_bytes(self.enc_demographics))

    def store_answers(self, survey_key: bytes, answers: dict):
        """
        Encrypt and store survey answers (for patient data surveys).

        Args:
            survey_key: Survey's KEK (32-byte key)
            answers: Dictionary of question_id -> answer

        This encrypts the entire answers dictionary, providing complete
        protection for surveys collecting patient data.
        """
        self.enc_answers = encrypt_sensitive(survey_key, answers)
        # Clear plaintext answers when encrypting
        self.answers = {}

    def load_answers(self, survey_key: bytes) -> dict:
        """
        Decrypt and return survey answers.

        Args:
            survey_key: Survey's KEK (32-byte key)

        Returns:
            Dictionary of question_id -> answer

        If answers are not encrypted, returns the plaintext answers field.
        """
        if self.enc_answers:
            return decrypt_sensitive(survey_key, self._to_bytes(self.enc_answers))
        return self.answers

    def store_complete_response(
        self, survey_key: bytes, answers: dict, demographics: dict | None = None
    ):
        """
        Store a complete encrypted response (answers + demographics).

        Args:
            survey_key: Survey's KEK (32-byte key)
            answers: Dictionary of question_id -> answer
            demographics: Optional patient demographics

        This is the preferred method for patient data surveys - encrypts
        everything in one consistent format.
        """
        # Combine into single encrypted blob
        full_response = {"answers": answers}
        if demographics:
            full_response["demographics"] = demographics

        self.enc_answers = encrypt_sensitive(survey_key, full_response)
        # Clear plaintext fields
        self.answers = {}
        self.enc_demographics = None

    def load_complete_response(self, survey_key: bytes) -> dict:
        """
        Load a complete decrypted response.

        Args:
            survey_key: Survey's KEK (32-byte key)

        Returns:
            Dictionary with 'answers' and optionally 'demographics' keys

        Falls back to legacy format if enc_answers not present.
        """
        if self.enc_answers:
            return decrypt_sensitive(survey_key, self._to_bytes(self.enc_answers))

        # Legacy format: separate fields
        result = {"answers": self.answers}
        if self.enc_demographics:
            result["demographics"] = self.load_demographics(survey_key)
        return result

    @property
    def is_encrypted(self) -> bool:
        """Check if this response has encrypted data."""
        return bool(self.enc_answers or self.enc_demographics)

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
    for_authenticated = models.BooleanField(
        default=False,
        help_text="True if this token is for authenticated user invitation (not anonymous token)",
    )

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


class LLMConversationSession(models.Model):
    """
    Stores LLM conversation sessions for AI-assisted survey generation.
    Allows users to continue conversations across requests.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="llm_conversations"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="llm_conversations"
    )

    # Conversation state
    conversation_history = models.JSONField(
        default=list,
        help_text="List of {role, content, timestamp} message dictionaries",
    )
    current_markdown = models.TextField(
        blank=True, help_text="Latest generated markdown"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Only one active session per user-survey pair",
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["survey", "user", "-updated_at"]),
            models.Index(fields=["is_active", "-updated_at"]),
        ]
        verbose_name = "LLM Conversation Session"
        verbose_name_plural = "LLM Conversation Sessions"

    def __str__(self):
        return f"LLM Session for {self.survey.name} by {self.user.username}"

    def add_message(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append(
            {"role": role, "content": content, "timestamp": timezone.now().isoformat()}
        )
        self.save()

    def get_conversation_for_llm(self) -> list:
        """Get conversation history in LLM format (without timestamps)."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_history
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


# ============================================================================
# DataSet Models - Dropdown List Management
# ============================================================================


class DataSet(models.Model):
    """
    Unified model for all dropdown datasets.

    Supports:
    - NHS Data Dictionary standardized lists (read-only)
    - External API datasets (synced periodically)
    - User-created custom lists
    - Customized versions of NHS DD lists (based on parent)

    NHS DD lists are the gold standard - they cannot be edited directly.
    Users can create custom versions based on NHS DD lists as templates.
    """

    CATEGORY_CHOICES = [
        ("nhs_dd", "NHS Data Dictionary"),
        ("external_api", "External API"),
        ("user_created", "User Created"),
        ("rcpch", "RCPCH API"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("api", "External API"),
        ("manual", "Manual Entry"),
        ("imported", "Imported from File"),
        ("scrape", "Web Scraping"),
    ]

    # Identity
    key = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier for this dataset (e.g., 'main_specialty_codes')",
    )
    name = models.CharField(
        max_length=255, help_text="Display name (e.g., 'Main Specialty Codes')"
    )
    description = models.TextField(blank=True)

    # Categorization
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="user_created",
        db_index=True,
        help_text="Category of this dataset",
    )

    # Source tracking
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="manual",
        help_text="How this dataset was created",
    )

    # NHS DD / Reference information
    reference_url = models.URLField(
        blank=True,
        help_text="Source reference URL (e.g., NHS Data Dictionary page)",
    )
    nhs_dd_page_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="NHS DD page identifier for tracking updates",
    )

    # Custom vs Standard flag
    is_custom = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False for standard NHS DD lists (read-only), True for user-created/customized",
    )

    # Parent relationship - for customized versions of NHS DD lists
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customizations",
        help_text="Parent dataset if this is a customized version",
    )

    # For API-sourced datasets
    external_api_endpoint = models.CharField(
        max_length=255,
        blank=True,
        help_text="API endpoint path for external datasets",
    )
    external_api_url = models.URLField(
        blank=True, help_text="Full API URL if different from default"
    )
    sync_frequency_hours = models.IntegerField(
        default=24,
        null=True,
        blank=True,
        help_text="How often to sync from external API (hours)",
    )
    last_synced_at = models.DateTimeField(
        null=True, blank=True, help_text="Last successful sync from API"
    )

    # For web scraping
    last_scraped = models.DateTimeField(
        null=True, blank=True, help_text="Last successful scrape from source URL"
    )
    nhs_dd_published_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the NHS DD list was published (if available)",
    )

    # Sharing and ownership
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="datasets",
        help_text="Organization that owns this dataset (null = global/platform-wide)",
    )
    is_global = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True for platform-wide datasets available to all users",
    )

    # Data storage
    options = models.JSONField(
        default=list,
        help_text="List of option strings for dropdown display",
    )

    # Format specification (for display and parsing)
    format_pattern = models.CharField(
        max_length=50,
        blank=True,
        help_text="Format pattern: 'CODE - NAME', 'NAME (CODE)', 'CODE | NAME', etc.",
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_datasets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(
        default=1, help_text="Version number, incremented on updates"
    )

    # Publishing tracking
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this dataset was published globally (if applicable)",
    )

    # Tags for discovery and filtering
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for categorization and filtering (e.g., ['medical', 'NHS', 'England'])",
    )

    # Active flag for soft deletion
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False to hide dataset without deleting",
    )

    class Meta:
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["is_global", "is_active"]),
            models.Index(fields=["last_synced_at"]),
            models.Index(fields=["is_custom"]),
            models.Index(fields=["published_at"]),
        ]
        constraints = [
            # NHS DD lists must be global and not have an organization
            models.CheckConstraint(
                condition=~models.Q(category="nhs_dd", organization__isnull=False),
                name="nhs_dd_must_be_global",
            ),
            # Platform global datasets (not published) cannot have an organization
            # Published datasets CAN have organization for attribution
            models.CheckConstraint(
                condition=~models.Q(
                    is_global=True,
                    organization__isnull=False,
                    published_at__isnull=True,
                ),
                name="platform_global_datasets_no_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.key})"

    @property
    def is_editable(self) -> bool:
        """NHS DD standard lists are read-only, custom lists are editable."""
        return self.is_custom

    @property
    def needs_sync(self) -> bool:
        """Check if this API-sourced dataset needs syncing."""
        if self.source_type != "api" or not self.sync_frequency_hours:
            return False

        if not self.last_synced_at:
            return True

        from django.utils import timezone

        next_sync = self.last_synced_at + timezone.timedelta(
            hours=self.sync_frequency_hours
        )
        return timezone.now() >= next_sync

    def create_custom_version(
        self, user: User, organization: Organization, custom_name: str = None
    ) -> "DataSet":
        """
        Create a customized version of this dataset.

        Allowed for any global dataset. Creates a copy that user can edit.

        Args:
            user: User creating the custom version
            organization: Organization to own the custom version (can be None for individual users)
            custom_name: Optional custom name (defaults to "{name} (Custom)")

        Returns:
            New DataSet instance as a custom version

        Raises:
            ValueError: If this dataset is not global
        """
        if not self.is_global:
            raise ValueError("Can only create custom versions of global datasets")

        # Generate unique key for custom version
        import time

        if organization:
            custom_key = f"{self.key}_custom_{organization.id}_{int(time.time())}"
        else:
            # Individual user custom version
            custom_key = f"{self.key}_custom_u{user.id}_{int(time.time())}"

        return DataSet.objects.create(
            key=custom_key,
            name=custom_name or f"{self.name} (Custom)",
            description=f"Customized version of {self.name}\n\n{self.description}",
            category="user_created",  # Custom versions are always user_created
            source_type="manual",
            is_custom=True,
            parent=self,
            organization=organization,  # Can be None for individual users
            is_global=False,
            options=self.options.copy(),  # Start with parent's options
            format_pattern=self.format_pattern,
            tags=self.tags.copy() if self.tags else [],  # Inherit tags
            created_by=user,
        )

    def publish(self) -> None:
        """
        Publish this dataset globally.

        Makes a dataset available to all users.
        Can be called on organization-owned or individual user datasets.
        Sets published_at timestamp and makes dataset global.

        Raises:
            ValueError: If dataset is already global or is NHS DD
        """
        from django.utils import timezone

        if self.is_global:
            raise ValueError("Dataset is already published globally")

        if self.category == "nhs_dd":
            raise ValueError("NHS Data Dictionary datasets cannot be published")

        # Make global and track when published
        self.is_global = True
        self.published_at = timezone.now()
        # Keep organization reference for attribution (can be None for individual users)
        self.save(update_fields=["is_global", "published_at", "updated_at"])

    def has_dependents(self) -> bool:
        """
        Check if other users/organizations have created custom versions from this dataset.

        Returns True if there are any custom versions created by different users/organizations,
        indicating that others depend on this dataset.

        Returns:
            bool: True if dependents exist, False otherwise
        """
        if not self.is_global:
            return False

        # Get all custom versions
        dependents = DataSet.objects.filter(
            parent=self,
            is_active=True,
        )

        # Exclude dependents from the same organization (if org-owned)
        # or created by the same user (if individual)
        if self.organization:
            dependents = dependents.exclude(organization=self.organization)
        else:
            # Individual user dataset - exclude versions by same user
            dependents = dependents.exclude(
                created_by=self.created_by, organization__isnull=True
            )

        return dependents.count() > 0

    def increment_version(self) -> None:
        """Increment version number when dataset is updated."""
        self.version += 1
        self.save(update_fields=["version", "updated_at"])


# ============================================================================
# Recovery Request Models - Ethical Data Recovery
# ============================================================================


class RecoveryRequest(models.Model):
    """
    Tracks recovery requests for users who have lost both password and recovery phrase.

    Implements the ethical recovery workflow with:
    - Identity verification (photo ID, video call, security questions)
    - Dual administrator authorization (two different admins must approve)
    - Time delay (24-48 hours after approval before execution)
    - Full audit trail for regulatory compliance

    This enables data recovery while preventing unauthorized access through
    multiple layers of verification and mandatory waiting periods.
    """

    class Status(models.TextChoices):
        PENDING_VERIFICATION = "pending_verification", "Pending Identity Verification"
        VERIFICATION_IN_PROGRESS = (
            "verification_in_progress",
            "Identity Verification In Progress",
        )
        AWAITING_PRIMARY = "awaiting_primary", "Awaiting Primary Authorization"
        AWAITING_SECONDARY = "awaiting_secondary", "Awaiting Secondary Authorization"
        IN_TIME_DELAY = "in_time_delay", "In Time Delay Period"
        READY_FOR_EXECUTION = "ready_for_execution", "Ready for Execution"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    # Primary key as UUID for non-sequential, secure identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Human-readable request ID (e.g., ABC-123-XYZ)
    request_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Human-readable request code for reference",
    )

    # User requesting recovery
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recovery_requests"
    )
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE, related_name="recovery_requests"
    )

    # Current status
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING_VERIFICATION
    )

    # Timestamps for workflow stages
    submitted_at = models.DateTimeField(auto_now_add=True)
    verification_completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(
        null=True, blank=True, help_text="When both approvals completed"
    )
    time_delay_until = models.DateTimeField(
        null=True, blank=True, help_text="Recovery can execute after this time"
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    # Time delay configuration (depends on user tier)
    time_delay_hours = models.PositiveIntegerField(
        default=48,
        help_text="Hours to wait after approval before execution (24h org, 48h individual)",
    )

    # Primary authorization
    primary_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_primary_approvals",
    )
    primary_approved_at = models.DateTimeField(null=True, blank=True)
    primary_reason = models.TextField(
        blank=True, help_text="Primary approver's verification notes"
    )

    # Secondary authorization (must be different admin)
    secondary_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_secondary_approvals",
    )
    secondary_approved_at = models.DateTimeField(null=True, blank=True)
    secondary_reason = models.TextField(
        blank=True, help_text="Secondary approver's verification notes"
    )

    # Rejection details
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_rejections",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Cancellation details
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_cancellations",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Execution details
    executed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_executions",
    )
    custodian_component_used = models.BooleanField(
        default=False,
        help_text="Whether platform custodian component was used for recovery",
    )

    # Vault path for escrowed key
    vault_recovery_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Vault path to escrowed recovery key",
    )

    # User context at time of request (for verification)
    user_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="User details captured at request time (email, account age, etc.)",
    )

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "-submitted_at"]),
            models.Index(fields=["user", "-submitted_at"]),
            models.Index(fields=["survey", "-submitted_at"]),
            models.Index(fields=["time_delay_until"]),
            models.Index(fields=["request_code"]),
        ]

    def __str__(self) -> str:
        return f"Recovery Request {self.request_code} - {self.user.email}"

    def save(self, *args, **kwargs):
        """Generate request code on first save."""
        if not self.request_code:
            self.request_code = self._generate_request_code()
        super().save(*args, **kwargs)

    def _generate_request_code(self) -> str:
        """Generate human-readable request code like ABC-123-XYZ."""
        import random
        import string

        chars = string.ascii_uppercase
        digits = string.digits

        part1 = "".join(random.choices(chars, k=3))
        part2 = "".join(random.choices(digits, k=3))
        part3 = "".join(random.choices(chars, k=3))

        return f"{part1}-{part2}-{part3}"

    def approve_primary(self, admin: User, reason: str) -> None:
        """Record primary approval."""
        if self.status != self.Status.AWAITING_PRIMARY:
            raise ValueError(
                f"Cannot approve: status is {self.status}, expected awaiting_primary"
            )

        self.primary_approver = admin
        self.primary_approved_at = timezone.now()
        self.primary_reason = reason
        self.status = self.Status.AWAITING_SECONDARY
        self.save()

        # Log to audit trail
        self._create_audit_entry(
            event_type="primary_approval",
            actor=admin,
            details={"reason": reason},
        )

    def approve_secondary(self, admin: User, reason: str) -> None:
        """Record secondary approval and start time delay."""
        if self.status != self.Status.AWAITING_SECONDARY:
            raise ValueError(
                f"Cannot approve: status is {self.status}, expected awaiting_secondary"
            )

        if admin == self.primary_approver:
            raise ValueError("Secondary approver must be different from primary")

        from datetime import timedelta

        self.secondary_approver = admin
        self.secondary_approved_at = timezone.now()
        self.secondary_reason = reason
        self.approved_at = timezone.now()
        self.time_delay_until = timezone.now() + timedelta(hours=self.time_delay_hours)
        self.status = self.Status.IN_TIME_DELAY
        self.save()

        # Log to audit trail
        self._create_audit_entry(
            event_type="secondary_approval",
            actor=admin,
            details={
                "reason": reason,
                "time_delay_until": self.time_delay_until.isoformat(),
            },
        )

        # Schedule time delay completion check (will be done via Celery in production)
        # send_time_delay_notification.apply_async(eta=self.time_delay_until)

    def reject(self, admin: User, reason: str) -> None:
        """Reject the recovery request."""
        self.rejected_by = admin
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.status = self.Status.REJECTED
        self.save()

        self._create_audit_entry(
            event_type="rejection",
            actor=admin,
            details={"reason": reason},
        )

    def cancel(self, user: User, reason: str) -> None:
        """Cancel the recovery request (user or admin)."""
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.status = self.Status.CANCELLED
        self.save()

        self._create_audit_entry(
            event_type="cancellation",
            actor=user,
            details={"reason": reason},
        )

    def check_time_delay_complete(self) -> bool:
        """Check if time delay has passed and update status if needed."""
        if self.status != self.Status.IN_TIME_DELAY:
            return False

        if self.time_delay_until and timezone.now() >= self.time_delay_until:
            self.status = self.Status.READY_FOR_EXECUTION
            self.save(update_fields=["status"])

            self._create_audit_entry(
                event_type="time_delay_complete",
                actor=None,  # System action
                details={"time_delay_hours": self.time_delay_hours},
            )

            return True

        return False

    def execute_recovery(self, admin: User, new_password: str) -> bytes:
        """
        Execute the recovery - decrypt escrowed KEK and re-encrypt with new password.

        Returns the recovered survey KEK.
        """
        if self.status != self.Status.READY_FOR_EXECUTION:
            raise ValueError(
                f"Cannot execute: status is {self.status}, expected ready_for_execution"
            )

        from django.conf import settings

        from .vault_client import get_vault_client

        vault = get_vault_client()
        custodian_component = bytes.fromhex(settings.PLATFORM_CUSTODIAN_COMPONENT)

        # Recover KEK from Vault
        survey_kek = vault.recover_user_survey_kek(
            user_id=self.user.id,
            survey_id=self.survey.id,
            admin_id=admin.id,
            verification_notes=f"Recovery request {self.request_code}",
            platform_custodian_component=custodian_component,
        )

        # Re-encrypt with new password
        from .utils import encrypt_kek_with_passphrase

        self.survey.encrypted_kek_password = encrypt_kek_with_passphrase(
            survey_kek, new_password
        )
        self.survey.save(update_fields=["encrypted_kek_password"])

        # Update request status
        self.executed_by = admin
        self.custodian_component_used = True
        self.completed_at = timezone.now()
        self.status = self.Status.COMPLETED
        self.save()

        self._create_audit_entry(
            event_type="recovery_executed",
            actor=admin,
            details={
                "survey_id": self.survey.id,
                "custodian_used": True,
            },
            severity="critical",
        )

        return survey_kek

    @property
    def time_remaining(self):
        """Get time remaining in delay period."""
        if self.status != self.Status.IN_TIME_DELAY or not self.time_delay_until:
            return None

        remaining = self.time_delay_until - timezone.now()
        if remaining.total_seconds() < 0:
            return None

        return remaining

    @property
    def is_verification_complete(self) -> bool:
        """Check if all required identity verifications are complete."""
        verifications = self.identity_verifications.filter(status="verified")

        # Require at least photo_id and one of video_call or security_questions
        has_photo_id = verifications.filter(verification_type="photo_id").exists()
        has_video_or_questions = verifications.filter(
            verification_type__in=["video_call", "security_questions"]
        ).exists()

        return has_photo_id and has_video_or_questions

    def _create_audit_entry(
        self, event_type: str, actor: User | None, details: dict, severity: str = "info"
    ) -> "RecoveryAuditEntry":
        """Create an audit entry for this recovery request."""
        return RecoveryAuditEntry.objects.create(
            recovery_request=self,
            event_type=event_type,
            severity=severity,
            actor_type=(
                "system"
                if actor is None
                else (
                    "admin" if hasattr(actor, "is_staff") and actor.is_staff else "user"
                )
            ),
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            details=details,
        )


class IdentityVerification(models.Model):
    """
    Tracks identity verification steps for recovery requests.

    Supports multiple verification methods:
    - Photo ID (government-issued identification)
    - Video call (live verification by admin)
    - Security questions (questions about account/data)
    - Employment verification (for org users)
    """

    class VerificationType(models.TextChoices):
        PHOTO_ID = "photo_id", "Photo ID"
        VIDEO_CALL = "video_call", "Video Verification Call"
        SECURITY_QUESTIONS = "security_questions", "Security Questions"
        EMPLOYMENT_VERIFICATION = "employment_verification", "Employment Verification"
        SSO_REAUTHENTICATION = "sso_reauth", "SSO Re-authentication"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_request = models.ForeignKey(
        RecoveryRequest, on_delete=models.CASCADE, related_name="identity_verifications"
    )
    verification_type = models.CharField(
        max_length=50, choices=VerificationType.choices
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    # Document storage (path to encrypted file, not stored in DB)
    document_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Encrypted storage path for uploaded documents",
    )
    document_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of document (e.g., UK Driving Licence)",
    )

    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Verification by admin
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="identity_verifications",
    )
    verification_notes = models.TextField(
        blank=True, help_text="Admin notes on verification"
    )

    # For video calls
    video_call_scheduled_at = models.DateTimeField(null=True, blank=True)
    video_call_duration_minutes = models.IntegerField(null=True, blank=True)
    video_recording_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to encrypted video recording (if enabled)",
    )

    # For security questions
    questions_asked = models.JSONField(
        default=list, blank=True, help_text="List of questions asked"
    )
    correct_answers = models.IntegerField(
        null=True, blank=True, help_text="Number of correct answers"
    )
    total_questions = models.IntegerField(
        null=True, blank=True, help_text="Total questions asked"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Auto-deletion tracking
    auto_delete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Documents auto-deleted 30 days after request completion",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["recovery_request", "verification_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["auto_delete_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_verification_type_display()} - {self.get_status_display()}"

    def submit_document(self, document_path: str, document_type: str = "") -> None:
        """Record document submission."""
        self.document_path = document_path
        self.document_type = document_type
        self.submitted_at = timezone.now()
        self.status = self.Status.SUBMITTED
        self.save()

    def verify(self, admin: User, notes: str) -> None:
        """Mark verification as complete."""
        self.verified_by = admin
        self.verification_notes = notes
        self.verified_at = timezone.now()
        self.status = self.Status.VERIFIED
        self.save()

        # Check if all verifications complete and update parent request
        request = self.recovery_request
        if request.is_verification_complete and request.status in [
            RecoveryRequest.Status.PENDING_VERIFICATION,
            RecoveryRequest.Status.VERIFICATION_IN_PROGRESS,
        ]:
            request.verification_completed_at = timezone.now()
            request.status = RecoveryRequest.Status.AWAITING_PRIMARY
            request.save()

    def reject(self, admin: User, notes: str) -> None:
        """Reject this verification (user must resubmit)."""
        self.verified_by = admin
        self.verification_notes = notes
        self.verified_at = timezone.now()
        self.status = self.Status.REJECTED
        self.save()

    def schedule_auto_deletion(self) -> None:
        """Schedule document auto-deletion 30 days after request completion."""
        from datetime import timedelta

        if self.recovery_request.completed_at:
            self.auto_delete_at = self.recovery_request.completed_at + timedelta(
                days=30
            )
            self.save(update_fields=["auto_delete_at"])


class RecoveryAuditEntry(models.Model):
    """
    Immutable audit trail for recovery request actions.

    Every action on a recovery request is logged here for:
    - Regulatory compliance (GDPR, NHS IG)
    - Security monitoring and alerting
    - Dispute resolution
    - SIEM integration

    Entries include cryptographic hashes for tamper detection.
    """

    class Severity(models.TextChoices):
        INFO = "info", "Information"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recovery_request = models.ForeignKey(
        RecoveryRequest, on_delete=models.CASCADE, related_name="audit_entries"
    )

    # Timestamp (cannot be modified)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Event details
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of event (e.g., request_submitted, primary_approval, recovery_executed)",
    )
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.INFO
    )

    # Actor information
    actor_type = models.CharField(
        max_length=20,
        help_text="user, admin, or system",
    )
    actor_id = models.IntegerField(null=True, blank=True)
    actor_email = models.EmailField(null=True, blank=True)
    actor_ip = models.GenericIPAddressField(null=True, blank=True)
    actor_user_agent = models.TextField(blank=True)

    # Event details (JSON for flexibility)
    details = models.JSONField(default=dict)

    # Cryptographic integrity
    entry_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of entry for tamper detection",
    )
    previous_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="Hash of previous entry in chain",
    )

    # SIEM forwarding status
    forwarded_to_siem = models.BooleanField(default=False)
    forwarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["recovery_request", "-timestamp"]),
            models.Index(fields=["event_type", "-timestamp"]),
            models.Index(fields=["severity", "-timestamp"]),
            models.Index(fields=["actor_id"]),
            models.Index(fields=["forwarded_to_siem"]),
        ]
        # Prevent deletion of audit entries
        verbose_name = "Recovery Audit Entry"
        verbose_name_plural = "Recovery Audit Entries"

    def __str__(self) -> str:
        return f"{self.timestamp} - {self.event_type}"

    def save(self, *args, **kwargs):
        """Generate entry hash on save."""
        if not self.entry_hash:
            self._generate_hash()
        super().save(*args, **kwargs)

    def _generate_hash(self) -> None:
        """Generate SHA-256 hash of entry content."""
        import hashlib
        import json

        # Get previous entry hash
        previous = (
            RecoveryAuditEntry.objects.filter(recovery_request=self.recovery_request)
            .exclude(id=self.id)
            .order_by("-timestamp")
            .first()
        )

        self.previous_hash = previous.entry_hash if previous else ""

        # Create hash of entry content
        content = {
            "recovery_request_id": str(self.recovery_request_id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "event_type": self.event_type,
            "severity": self.severity,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }

        content_str = json.dumps(content, sort_keys=True)
        self.entry_hash = hashlib.sha256(content_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify this entry hasn't been tampered with."""
        import hashlib
        import json

        content = {
            "recovery_request_id": str(self.recovery_request_id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "event_type": self.event_type,
            "severity": self.severity,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }

        content_str = json.dumps(content, sort_keys=True)
        computed_hash = hashlib.sha256(content_str.encode()).hexdigest()

        return computed_hash == self.entry_hash

    def to_siem_format(self) -> dict:
        """Format entry for SIEM forwarding (Elasticsearch, Splunk, etc.)."""
        return {
            "@timestamp": self.timestamp.isoformat(),
            "event": {
                "kind": "event",
                "category": ["authentication", "iam"],
                "type": [self.event_type],
                "severity": self.severity,
            },
            "checktick": {
                "recovery_request": {
                    "id": str(self.recovery_request_id),
                    "code": self.recovery_request.request_code,
                    "user_id": self.recovery_request.user_id,
                    "survey_id": self.recovery_request.survey_id,
                },
                "audit_entry": {
                    "id": str(self.id),
                    "event_type": self.event_type,
                    "details": self.details,
                    "entry_hash": self.entry_hash,
                },
            },
            "user": {
                "type": self.actor_type,
                "id": str(self.actor_id) if self.actor_id else None,
                "email": self.actor_email,
            },
            "source": {
                "ip": self.actor_ip,
                "user_agent": self.actor_user_agent,
            },
        }
