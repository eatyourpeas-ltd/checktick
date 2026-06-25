#!/usr/bin/env python3
"""
Django management command to prune users who have not confirmed their email addresses.

This command should be run daily (e.g., via cron or scheduled job) to:
1. Deactivate existing users whose grace period has expired without confirmation
2. Delete new signups that never confirmed and have no meaningful data

Policy:
- Existing users (created before the email confirmation feature) are deactivated
  after a configurable grace period (default 30 days). Their data is preserved.
- New signups (created after the email confirmation feature) with no surveys,
  memberships, or audit history are deleted after the same grace period.
  This removes fake/phishing accounts that cannot access protected features.

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

from checktick_app.surveys.models import AuditLog

logger = logging.getLogger(__name__)

# Default grace period for unconfirmed accounts (days)
DEFAULT_GRACE_DAYS = 30

# Users created before this date are treated as "existing" (pre-feature)
# This is set to the deployment date of the email confirmation feature.
# Adjust this constant when deploying to production.
FEATURE_CUTOFF_DATE = getattr(
    settings,
    "EMAIL_CONFIRMATION_CUTOFF",
    timezone.make_aware(timezone.datetime(2025, 6, 25)),
)

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


class Command(BaseCommand):
    help = (
        "Prune unconfirmed users: deactivate existing users and delete "
        "new signups with no data after grace period"
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

        self.stdout.write(
            self.style.SUCCESS(f"Starting unconfirmed user pruning at {timezone.now()}")
        )
        self.stdout.write(f"  Grace period: {grace_days} days")
        self.stdout.write(f"  Feature cutoff: {FEATURE_CUTOFF_DATE.date()}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        cutoff = timezone.now() - timedelta(days=grace_days)

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
                f"Found {unconfirmed_users.count()} unconfirmed users past grace period"
            )

        deactivated = 0
        deleted = 0
        skipped = 0

        for user in unconfirmed_users:
            is_existing_user = user.date_joined < FEATURE_CUTOFF_DATE
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

        self.stdout.write(
            self.style.SUCCESS(f"\nPruning completed at {timezone.now()}")
        )
        self.stdout.write(f"  - Deactivated: {deactivated}")
        self.stdout.write(f"  - Deleted:     {deleted}")
        self.stdout.write(f"  - Skipped:     {skipped}")
