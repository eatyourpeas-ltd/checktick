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
                check=(
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
                        target_group=condition.target_group,
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
                check=~models.Q(category="nhs_dd", organization__isnull=False),
                name="nhs_dd_must_be_global",
            ),
            # Platform global datasets (not published) cannot have an organization
            # Published datasets CAN have organization for attribution
            models.CheckConstraint(
                check=~models.Q(
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
