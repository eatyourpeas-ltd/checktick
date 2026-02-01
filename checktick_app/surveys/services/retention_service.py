"""
RetentionService - Handles retention periods, deletion warnings, and automatic cleanup.

Features:
- Calculate deletion dates based on retention policy
- Send deletion warnings (30 days, 7 days, 1 day before)
- Handle automatic soft deletion after retention period
- Handle automatic hard deletion after grace period
- Respect legal holds (prevent deletion)
- Secure cryptographic key erasure for hard deletion
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from ..models import Survey

    UserType = AbstractUser
else:
    UserType = object

User = get_user_model()
logger = logging.getLogger(__name__)


class RetentionService:
    """
    Service for managing survey data retention and deletion.

    Retention Policy:
    - Default retention: 6 months after survey closure
    - Maximum retention: 24 months after survey closure
    - Soft deletion grace period: 30 days
    - Legal holds: Prevent all automatic deletion

    Workflow:
    1. Survey is closed -> deletion_date = closed_at + retention_months
    2. At deletion_date-30d -> send warning email
    3. At deletion_date-7d -> send warning email
    4. At deletion_date-1d -> send warning email
    5. At deletion_date -> soft delete (set deleted_at)
    6. At deleted_at+30d -> hard delete (permanent)

    Legal holds block all automatic deletion at any stage.
    """

    # Warning intervals before deletion
    WARNING_DAYS = [30, 7, 1]

    # Grace period for soft deletion
    SOFT_DELETE_GRACE_DAYS = 30

    # Default and maximum retention periods
    DEFAULT_RETENTION_MONTHS = 6
    MAX_RETENTION_MONTHS = 24

    @classmethod
    def calculate_deletion_date(
        cls, closed_at, retention_months: int = DEFAULT_RETENTION_MONTHS
    ):
        """
        Calculate when a survey should be deleted based on closure date.

        Args:
            closed_at: DateTime when survey was closed
            retention_months: Number of months to retain (6-24)

        Returns:
            DateTime when survey should be deleted
        """
        # Approximate: 1 month = 30 days
        retention_days = retention_months * 30
        return closed_at + timedelta(days=retention_days)

    @classmethod
    def get_surveys_pending_deletion_warning(cls, days_before: int) -> list[Survey]:
        """
        Get surveys that need deletion warning emails.

        Args:
            days_before: Number of days before deletion (30, 7, or 1)

        Returns:
            QuerySet of surveys needing warnings
        """
        from ..models import Survey

        # Calculate the target date range
        warning_date = timezone.now() + timedelta(days=days_before)
        # Give a 1-day window for the warning
        date_from = warning_date - timedelta(hours=12)
        date_to = warning_date + timedelta(hours=12)

        # Find surveys with deletion_date in the warning window
        surveys = Survey.objects.filter(
            deletion_date__gte=date_from,
            deletion_date__lte=date_to,
            deleted_at__isnull=True,  # Not already deleted
        ).exclude(
            legal_hold__isnull=False,  # No legal hold
            legal_hold__removed_at__isnull=True,
        )

        # Warnings sent daily via cron (process_data_governance command)
        # Within 24-hour window avoids duplicates

        return list(surveys)

    @classmethod
    def send_deletion_warning(cls, survey: Survey, days_remaining: int) -> None:
        """
        Send email warning about upcoming deletion.

        Args:
            survey: Survey approaching deletion
            days_remaining: Days until automatic deletion
        """
        from django.template.loader import render_to_string

        from checktick_app.core.email_utils import (
            get_platform_branding,
            send_branded_email,
        )

        owner_email = survey.owner.email

        # Determine urgency level for messaging
        if days_remaining <= 1:
            urgency = "URGENT"
            timeframe = "tomorrow" if days_remaining == 1 else "today"
        elif days_remaining <= 7:
            urgency = "Important"
            timeframe = f"in {days_remaining} days"
        else:
            urgency = "Notice"
            timeframe = f"in {days_remaining} days"

        subject = (
            f"{urgency}: Survey Data Deletion Warning - {days_remaining} days remaining"
        )

        branding = get_platform_branding()

        markdown_content = render_to_string(
            "emails/data_governance/deletion_warning.md",
            {
                "survey": survey,
                "urgency": urgency,
                "timeframe": timeframe,
                "deletion_date": survey.deletion_date.strftime("%B %d, %Y at %I:%M %p"),
                "closure_date": survey.closed_at.strftime("%B %d, %Y"),
                "days_remaining": days_remaining,
                "brand_title": branding["title"],
                "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            },
        )

        send_branded_email(
            to_email=owner_email,
            subject=subject,
            markdown_content=markdown_content,
            branding=branding,
        )

    @classmethod
    def send_retention_extension_email(
        cls,
        survey: Survey,
        extended_by: UserType,
        months_added: int,
        old_deletion_date: timezone.datetime,
        new_deletion_date: timezone.datetime,
        reason: str,
    ) -> None:
        """
        Send email notification when retention period is extended.

        Args:
            survey: Survey with extended retention
            extended_by: User who extended retention
            months_added: Number of months added
            old_deletion_date: Previous deletion date
            new_deletion_date: New deletion date
            reason: Justification for extension
        """
        from django.template.loader import render_to_string

        from checktick_app.core.email_utils import (
            get_platform_branding,
            send_branded_email,
        )

        owner_email = survey.owner.email

        subject = f"Retention Extended: {survey.name}"

        branding = get_platform_branding()

        markdown_content = render_to_string(
            "emails/data_governance/retention_extended.md",
            {
                "survey": survey,
                "extended_by": extended_by,
                "old_deletion_date": old_deletion_date.strftime("%B %d, %Y"),
                "new_deletion_date": new_deletion_date.strftime("%B %d, %Y"),
                "months_added": months_added,
                "extension_date": timezone.now().strftime("%B %d, %Y at %I:%M %p"),
                "reason": reason,
                "brand_title": branding["title"],
                "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            },
        )

        send_branded_email(
            to_email=owner_email,
            subject=subject,
            markdown_content=markdown_content,
            branding=branding,
        )

        # Also email org owner if different
        if (
            survey.organization
            and survey.organization.owner
            and survey.organization.owner.email != owner_email
        ):
            send_branded_email(
                to_email=survey.organization.owner.email,
                subject=subject,
                markdown_content=markdown_content,
                branding=branding,
            )

    @classmethod
    def send_deletion_cancelled_email(
        cls, survey: Survey, cancelled_by: UserType
    ) -> None:
        """
        Send email notification when soft deletion is cancelled.

        Args:
            survey: Survey that was restored
            cancelled_by: User who cancelled the deletion
        """
        from django.template.loader import render_to_string

        from checktick_app.core.email_utils import (
            get_platform_branding,
            send_branded_email,
        )

        owner_email = survey.owner.email

        subject = f"Survey Deletion Cancelled: {survey.name}"

        branding = get_platform_branding()

        # Note: deleted_at should be cleared by now, but we can still reference closure
        markdown_content = render_to_string(
            "emails/data_governance/deletion_cancelled.md",
            {
                "survey": survey,
                "cancelled_by": cancelled_by,
                "deletion_date": "(cancelled)",
                "closure_date": (
                    survey.closed_at.strftime("%B %d, %Y")
                    if survey.closed_at
                    else "N/A"
                ),
                "cancellation_date": timezone.now().strftime("%B %d, %Y at %I:%M %p"),
                "brand_title": branding["title"],
                "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
            },
        )

        send_branded_email(
            to_email=owner_email,
            subject=subject,
            markdown_content=markdown_content,
            branding=branding,
        )

        # Also email org owner if different
        if (
            survey.organization
            and survey.organization.owner
            and survey.organization.owner.email != owner_email
        ):
            send_branded_email(
                to_email=survey.organization.owner.email,
                subject=subject,
                markdown_content=markdown_content,
                branding=branding,
            )

    @classmethod
    @transaction.atomic
    def process_automatic_deletions(cls) -> dict[str, int]:
        """
        Process all surveys due for automatic deletion.

        This should be run daily via Celery task.

        Returns:
            Dictionary with counts of soft and hard deletions
        """
        from ..models import Survey

        now = timezone.now()
        stats = {
            "soft_deleted": 0,
            "hard_deleted": 0,
            "skipped_legal_hold": 0,
        }

        # Find surveys past their deletion_date (need soft deletion)
        # First, find all candidates
        candidates_for_soft_delete = Survey.objects.filter(
            deletion_date__lte=now,
            deleted_at__isnull=True,
            closed_at__isnull=False,  # Must be closed
        )

        for survey in candidates_for_soft_delete:
            # Skip surveys with active legal holds
            if hasattr(survey, "legal_hold") and survey.legal_hold.is_active:
                stats["skipped_legal_hold"] += 1
                continue

            survey.soft_delete()
            stats["soft_deleted"] += 1

        # Find surveys past their hard_deletion_date (need permanent deletion)
        candidates_for_hard_delete = Survey.objects.filter(
            hard_deletion_date__lte=now,
            deleted_at__isnull=False,
        )

        for survey in candidates_for_hard_delete:
            # Skip surveys with active legal holds
            if hasattr(survey, "legal_hold") and survey.legal_hold.is_active:
                stats["skipped_legal_hold"] += 1
                continue

            survey.hard_delete()
            stats["hard_deleted"] += 1

        return stats

    @classmethod
    @transaction.atomic
    def extend_retention(
        cls,
        survey: Survey,
        months: int,
        user: UserType,
        reason: str,
    ) -> None:
        """
        Extend retention period for a survey.

        Args:
            survey: Survey to extend retention for
            months: Number of additional months (total must be ≤24)
            user: User requesting extension
            reason: Business justification

        Raises:
            ValueError: If extension would exceed 24 months or survey not closed
        """
        from ..models import DataRetentionExtension

        # Validate survey is closed
        if not survey.is_closed:
            raise ValueError("Cannot extend retention for unclosed survey")

        # Validate total retention doesn't exceed 24 months
        if not survey.can_extend_retention:
            raise ValueError(
                "Cannot extend retention beyond 24 months from closure date"
            )

        # Calculate new retention total
        new_total_months = survey.retention_months + months
        if new_total_months > cls.MAX_RETENTION_MONTHS:
            raise ValueError(
                f"Extension would exceed maximum {cls.MAX_RETENTION_MONTHS} months "
                f"(current: {survey.retention_months}, requested: {months})"
            )

        # Record previous deletion date
        previous_deletion_date = survey.deletion_date

        # Update survey retention
        survey.extend_retention(months, user, reason)

        # Create audit record
        DataRetentionExtension.objects.create(
            survey=survey,
            requested_by=user,
            previous_deletion_date=previous_deletion_date,
            new_deletion_date=survey.deletion_date,
            months_extended=months,
            reason=reason,
            approved_by=user,  # Auto-approved for now
            approved_at=timezone.now(),
        )

        # Send confirmation email to user about retention extension
        cls.send_retention_extension_email(
            survey=survey,
            extended_by=user,
            months_added=months,
            old_deletion_date=previous_deletion_date,
            new_deletion_date=survey.deletion_date,
            reason=reason,
        )

    @classmethod
    def get_retention_extension_history(cls, survey: Survey) -> list:
        """
        Get all retention extensions for a survey.

        Args:
            survey: Survey to get history for

        Returns:
            List of DataRetentionExtension records
        """
        from ..models import DataRetentionExtension

        return list(
            DataRetentionExtension.objects.filter(survey=survey).order_by(
                "-requested_at"
            )
        )

    @classmethod
    def can_survey_be_deleted(cls, survey: Survey) -> tuple[bool, str | None]:
        """
        Check if a survey can be deleted.

        Args:
            survey: Survey to check

        Returns:
            Tuple of (can_delete: bool, reason: str | None)
        """
        # Check for active legal hold
        if hasattr(survey, "legal_hold") and survey.legal_hold.is_active:
            return False, "Survey has an active legal hold"

        # Check if already deleted
        if survey.deleted_at:
            return False, "Survey is already deleted"

        return True, None

    @classmethod
    @transaction.atomic
    def cancel_soft_deletion(cls, survey: Survey, user: UserType) -> None:
        """
        Cancel a soft deletion before hard deletion occurs.

        Args:
            survey: Survey to restore
            user: User cancelling the deletion

        Raises:
            ValueError: If survey not soft deleted or already hard deleted
        """
        if not survey.deleted_at:
            raise ValueError("Survey is not deleted")

        if survey.hard_deletion_date and timezone.now() >= survey.hard_deletion_date:
            raise ValueError("Survey has already been permanently deleted")

        # Clear deletion timestamps
        survey.deleted_at = None
        survey.hard_deletion_date = None
        survey.save(update_fields=["deleted_at", "hard_deletion_date"])

        # Send confirmation email about deletion cancellation
        cls.send_deletion_cancelled_email(survey=survey, cancelled_by=user)
