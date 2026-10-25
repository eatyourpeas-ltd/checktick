#!/usr/bin/env python3
"""
Django management command to prune users who have not confirmed their email addresses.

This command should be run daily (e.g., via cron or scheduled job) to:
1. Send pre-removal warning emails at 7 days and 1 day before the grace period ends
2. Deactivate existing users whose grace period has expired without confirmation
3. Delete new signups that never confirmed and have no meaningful data

Policy:
- Existing users (created before the email confirmation feature) are deactivated
  after a configurable grace period (default 30 days). Their data is preserved.
- New signups (created after the email confirmation feature) with no surveys,
  memberships, or audit history are deleted after the same grace period.
  This removes fake/phishing accounts that cannot access protected features.
- Before the grace period expires, warning emails are sent 7 days and 1 day
  before removal. The email signposts the user to their profile page to
  resend the confirmation email, and to the platform support email
  (settings.DEFAULT_FROM_EMAIL) if they need help.

Usage:
    python manage.py prune_unconfirmed_users
    python manage.py prune_unconfirmed_users --dry-run
    python manage.py prune_unconfirmed_users --verbose
    python manage.py prune_unconfirmed_users --grace-days=14
"""

from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from checktick_app.core.email_utils import send_unconfirmed_account_warning_email
from checktick_app.surveys.models import AuditLog

logger = logging.getLogger(__name__)

# Default grace period for unconfirmed accounts (days)
DEFAULT_GRACE_DAYS = 30

# Warning windows: (stage_name, days_before_removal).
# Ordered from furthest-out to closest-in so the command can pick the
# most-advanced stage that should have been sent.
WARNING_WINDOWS = [
    ("1week", 7),
    ("1day", 1),
]

# Stage progression order (furthest to closest).
STAGE_ORDER = ["1week", "1day"]

# Users created before this date are treated as "existing" (pre-feature)
# This is set to the deployment date of the email confirmation feature.
# Adjust this constant when deploying to production.
#
# NOTE: this default is a constant, not evaluated at import time against
# settings — the effective cutoff is read from settings in handle() so that
# EMAIL_CONFIRMATION_CUTOFF overrides (and test isolation) work reliably.
DEFAULT_FEATURE_CUTOFF_DATE = timezone.make_aware(timezone.datetime(2025, 6, 25))

User = get_user_model()


def _user_has_meaningful_data(user) -> bool:
    """Check if a user has created any data that should prevent deletion."""
    return any(
        [
            user.surveys.exists(),
            user.survey_memberships.exists(),
            user.question_groups.exists(),
            user.team_memberships.exists(),
            user.org_memberships.exists(),
            user.audit_targets.exists(),
        ]
    )


def _stage_to_send(days_until_removal: int, current_stage: str) -> str | None:
    """Determine which warning stage should fire, if any.

    Returns the stage name to send, or None if no stage should fire now.
    Mirrors the logic in process_expiring_subscriptions._stage_to_send.
    """
    if current_stage:
        try:
            current_idx = STAGE_ORDER.index(current_stage)
        except ValueError:
            current_idx = -1
    else:
        current_idx = -1

    # Walk from closest-in (1day) to furthest-out (1week).
    for idx, (stage_name, days_before) in enumerate(reversed(WARNING_WINDOWS)):
        # reversed() gives 1day, 1week — idx 0=1day, 1=1week.
        # Map to STAGE_ORDER index: 1day=1, 1week=0.
        stage_order_idx = len(STAGE_ORDER) - 1 - idx
        if days_until_removal <= days_before:
            # Within this window. Skip if we already sent this stage
            # or a later (closer-in) stage.
            if current_idx >= stage_order_idx:
                continue
            return stage_name
    return None


class Command(BaseCommand):
    help = (
        "Prune unconfirmed users: send pre-removal warnings, then deactivate "
        "existing users and delete new signups with no data after grace period"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output",
        )
        parser.add_argument(
            "--grace-days",
            type=int,
            default=DEFAULT_GRACE_DAYS,
            help=f"Grace period in days before pruning (default: {DEFAULT_GRACE_DAYS})",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        grace_days = options["grace_days"]

        cutoff = timezone.now() - timedelta(days=grace_days)
        feature_cutoff_date = getattr(
            settings,
            "EMAIL_CONFIRMATION_CUTOFF",
            DEFAULT_FEATURE_CUTOFF_DATE,
        )

        self.stdout.write(
            self.style.SUCCESS(f"Starting unconfirmed user pruning at {timezone.now()}")
        )
        self.stdout.write(f"  Grace period: {grace_days} days")
        self.stdout.write(f"  Feature cutoff: {feature_cutoff_date.date()}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # --- 1. Send pre-removal warnings to users approaching the cutoff ---
        warnings_sent = self._send_warnings(
            cutoff, grace_days, dry_run, verbose
        )

        # --- 2. Prune users past the grace period ---
        deactivated, deleted = self._prune_users(
            cutoff, grace_days, feature_cutoff_date, dry_run, verbose
        )

        self.stdout.write(
            self.style.SUCCESS(f"\nPruning completed at {timezone.now()}")
        )
        self.stdout.write(f"  - Warnings sent: {warnings_sent}")
        self.stdout.write(f"  - Deactivated:   {deactivated}")
        self.stdout.write(f"  - Deleted:       {deleted}")

    def _send_warnings(self, cutoff, grace_days, dry_run, verbose) -> int:
        """Send 1-week and 1-day warnings to unconfirmed users approaching removal."""
        # Users within the warning window: not yet past grace period, but
        # within 7 days of it. i.e. date_joined is between (cutoff + 1s) and
        # (cutoff + 7 days). We use date_joined__gte=cutoff so users exactly
        # at the boundary are warned, not pruned, this run.
        warning_start = cutoff
        warning_end = cutoff + timedelta(days=WARNING_WINDOWS[0][1])

        warning_candidates = (
            User.objects.filter(
                profile__email_confirmed=False,
                is_active=True,
                date_joined__gte=warning_start,
                date_joined__lte=warning_end,
            )
            .exclude(is_superuser=True)
            .exclude(is_staff=True)
            .select_related("profile")
        )

        if verbose:
            self.stdout.write(
                f"\nFound {warning_candidates.count()} unconfirmed users in warning window"
            )

        sent = 0
        for user in warning_candidates:
            days_since_joined = (timezone.now() - user.date_joined).days
            days_until_removal = grace_days - days_since_joined
            current_stage = user.profile.unconfirmed_warning_stage or ""
            stage = _stage_to_send(days_until_removal, current_stage)

            if stage is None:
                if verbose:
                    self.stdout.write(
                        f"  Skip warning {user.username}: "
                        f"days_until_removal={days_until_removal}, "
                        f"stage={current_stage!r}"
                    )
                continue

            if verbose or dry_run:
                self.stdout.write(
                    f"\n  User: {user.username} ({user.email})"
                    f"\n    Joined: {user.date_joined.date()}"
                    f"\n    Days until removal: {days_until_removal}"
                    f"\n    Warning stage: {stage}"
                )

            if dry_run:
                sent += 1
                continue

            try:
                ok = send_unconfirmed_account_warning_email(
                    user=user,
                    days_until_removal=days_until_removal,
                    grace_days=grace_days,
                )
                if ok:
                    user.profile.unconfirmed_warning_sent_at = timezone.now()
                    user.profile.unconfirmed_warning_stage = stage
                    user.profile.save(
                        update_fields=[
                            "unconfirmed_warning_sent_at",
                            "unconfirmed_warning_stage",
                        ]
                    )
                    sent += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"    Warning sent: {user.username}")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"    Warning failed: {user.username}")
                    )
            except Exception as e:
                logger.error(
                    "Failed to send unconfirmed account warning to %s: %s",
                    user.email,
                    e,
                )
                self.stdout.write(
                    self.style.ERROR(f"    Warning failed: {user.username}: {e}")
                )

        return sent

    def _prune_users(self, cutoff, grace_days, feature_cutoff_date, dry_run, verbose):
        """Deactivate or delete unconfirmed users past the grace period."""
        # Find unconfirmed, active users whose grace period has expired
        unconfirmed_users = (
            User.objects.filter(
                profile__email_confirmed=False,
                is_active=True,
                date_joined__lt=cutoff,
            )
            .exclude(is_superuser=True)
            .exclude(is_staff=True)
            .select_related("profile")
        )

        if verbose:
            self.stdout.write(
                f"\nFound {unconfirmed_users.count()} unconfirmed users past grace period"
            )

        deactivated = 0
        deleted = 0

        for user in unconfirmed_users:
            is_existing_user = user.date_joined < feature_cutoff_date
            has_data = _user_has_meaningful_data(user)

            if verbose or dry_run:
                action = "DEACTIVATE" if is_existing_user or has_data else "DELETE"
                self.stdout.write(
                    f"\n  User: {user.username} ({user.email})"
                    f"\n    Joined: {user.date_joined.date()}"
                    f"\n    Existing user: {is_existing_user}"
                    f"\n    Has data: {has_data}"
                    f"\n    Action: {action}"
                )

            if dry_run:
                if is_existing_user or has_data:
                    deactivated += 1
                else:
                    deleted += 1
                continue

            if is_existing_user or has_data:
                # Deactivate: preserve data and audit trail
                user.is_active = False
                user.save(update_fields=["is_active"])

                AuditLog.log_security_event(
                    action=AuditLog.Action.USER_DEACTIVATED,
                    actor=None,
                    message=(
                        f"User {user.username} ({user.email}) deactivated "
                        f"due to unconfirmed email after {grace_days} days."
                    ),
                    severity=AuditLog.Severity.WARNING,
                    metadata={
                        "reason": "unconfirmed_email",
                        "grace_days": grace_days,
                        "date_joined": user.date_joined.isoformat(),
                        "is_existing_user": is_existing_user,
                        "has_data": has_data,
                    },
                    target_user=user,
                )
                logger.info(
                    "Deactivated unconfirmed user: %s (%s)", user.username, user.email
                )
                self.stdout.write(
                    self.style.WARNING(f"    Deactivated: {user.username}")
                )
                deactivated += 1
            else:
                # Delete: new signup with no meaningful data
                email = user.email
                username = user.username
                date_joined = user.date_joined.isoformat()

                with transaction.atomic():
                    AuditLog.log_security_event(
                        action=AuditLog.Action.USER_DELETED,
                        actor=None,
                        message=(
                            f"User {username} ({email}) deleted due to "
                            f"unconfirmed email after {grace_days} days."
                        ),
                        severity=AuditLog.Severity.INFO,
                        metadata={
                            "reason": "unconfirmed_email",
                            "grace_days": grace_days,
                            "date_joined": date_joined,
                            "email": email,
                        },
                        target_user=None,  # User is about to be deleted
                    )
                    user.delete()

                logger.info("Deleted unconfirmed user: %s (%s)", username, email)
                self.stdout.write(self.style.ERROR(f"    Deleted: {username}"))
                deleted += 1

        return deactivated, deleted
