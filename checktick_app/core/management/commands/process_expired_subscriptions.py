#!/usr/bin/env python3
"""
Django management command to process expired subscriptions.

This command should be run daily (e.g., via cron or scheduled job) to:
1. Downgrade users whose subscription has expired (past period end date)
2. Downgrade users who have been past_due for longer than the grace period

When downgrading, excess surveys are automatically CLOSED (locked, read-only)
rather than deleted. Users can still view and export data from closed surveys.

Usage:
    python manage.py process_expired_subscriptions
    python manage.py process_expired_subscriptions --dry-run
    python manage.py process_expired_subscriptions --verbose
    python manage.py process_expired_subscriptions --grace-days=10
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from checktick_app.core.email_utils import (
    send_subscription_cancelled_email,
    send_subscription_expired_email,
)
from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import Survey

logger = logging.getLogger(__name__)

# Default grace period for past due accounts (days)
DEFAULT_GRACE_PERIOD_DAYS = 7


class Command(BaseCommand):
    help = "Process expired subscriptions and downgrade users to FREE tier"

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
            default=DEFAULT_GRACE_PERIOD_DAYS,
            help=f"Grace period in days for past due accounts (default: {DEFAULT_GRACE_PERIOD_DAYS})",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        grace_days = options["grace_days"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting subscription expiry processing at {timezone.now()}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Skip if self-hosted (no billing)
        if getattr(settings, "SELF_HOSTED", False):
            self.stdout.write(
                self.style.WARNING("Self-hosted mode - billing is disabled, skipping")
            )
            return

        # Process expired subscriptions (past period end date)
        expired_count = self._process_expired_subscriptions(dry_run, verbose)

        # Process past due accounts (exceeded grace period)
        past_due_count = self._process_past_due_accounts(dry_run, verbose, grace_days)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSubscription processing completed at {timezone.now()}"
            )
        )
        self.stdout.write(f"  - Expired subscriptions processed: {expired_count}")
        self.stdout.write(f"  - Past due accounts processed: {past_due_count}")

    def _process_expired_subscriptions(self, dry_run, verbose):
        """Process subscriptions that have passed their period end date.

        This handles:
        - Cancelled subscriptions that reached their end date
        - Subscriptions with a set end date that has passed
        """
        self.stdout.write(self.style.HTTP_INFO("\n--- Expired Subscriptions ---"))

        now = timezone.now()

        # Find profiles with:
        # - subscription_current_period_end in the past
        # - status is canceled or active (not already downgraded)
        # - has a paid tier
        expired_profiles = UserProfile.objects.filter(
            subscription_current_period_end__lt=now,
            subscription_status__in=[
                UserProfile.SubscriptionStatus.CANCELED,
                UserProfile.SubscriptionStatus.ACTIVE,
            ],
        ).exclude(
            account_tier=UserProfile.AccountTier.FREE,
        )

        if verbose:
            self.stdout.write(f"Found {expired_profiles.count()} expired subscriptions")

        processed = 0
        for profile in expired_profiles:
            user = profile.user
            old_tier = profile.account_tier

            # Count surveys that will be closed
            survey_count = (
                Survey.objects.filter(owner=user)
                .exclude(status=Survey.Status.CLOSED)
                .count()
            )
            free_tier_limit = 3
            surveys_to_close = max(0, survey_count - free_tier_limit)

            if verbose or dry_run:
                self.stdout.write(
                    f"\n  User: {user.username} ({user.email})"
                    f"\n    Old tier: {old_tier}"
                    f"\n    Period ended: {profile.subscription_current_period_end}"
                    f"\n    Surveys to close: {surveys_to_close}"
                )

            if not dry_run:
                # Force downgrade to FREE (this closes excess surveys)
                success, message = profile.force_downgrade_tier(
                    UserProfile.AccountTier.FREE
                )

                if success:
                    # Update subscription status
                    profile.subscription_status = (
                        UserProfile.SubscriptionStatus.CANCELED
                    )
                    profile.payment_subscription_id = ""
                    profile.subscription_current_period_end = None
                    profile.save(
                        update_fields=[
                            "subscription_status",
                            "payment_subscription_id",
                            "subscription_current_period_end",
                            "updated_at",
                        ]
                    )

                    logger.info(
                        f"Expired subscription downgraded: {user.username} "
                        f"from {old_tier} to FREE, {surveys_to_close} surveys closed"
                    )

                    # Send email notification
                    try:
                        send_subscription_expired_email(
                            user=user,
                            old_tier=old_tier,
                            survey_count=survey_count,
                            surveys_closed=surveys_to_close,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send expiry email to {user.email}: {e}"
                        )

                    self.stdout.write(
                        self.style.SUCCESS(f"    ✓ Downgraded to FREE tier")
                    )
                else:
                    logger.error(f"Failed to downgrade {user.username}: {message}")
                    self.stdout.write(self.style.ERROR(f"    ✗ Failed: {message}"))

            processed += 1

        return processed

    def _process_past_due_accounts(self, dry_run, verbose, grace_days):
        """Process accounts that have been past due for too long.

        After the grace period, accounts are downgraded to FREE tier.
        Users still retain access until their period end date, but if
        we don't have a period end date, we use the grace period.
        """
        self.stdout.write(self.style.HTTP_INFO("\n--- Past Due Accounts ---"))

        now = timezone.now()
        grace_cutoff = now - timedelta(days=grace_days)

        # Find profiles that:
        # - Have been past_due status
        # - Were updated (became past_due) more than grace_days ago
        # - Don't have a future period end date (if they do, let that handle it)
        # - Still have a paid tier
        past_due_profiles = (
            UserProfile.objects.filter(
                subscription_status=UserProfile.SubscriptionStatus.PAST_DUE,
                updated_at__lt=grace_cutoff,
            )
            .exclude(
                account_tier=UserProfile.AccountTier.FREE,
            )
            .exclude(
                # Don't process if period end is in the future
                subscription_current_period_end__gt=now,
            )
        )

        if verbose:
            self.stdout.write(
                f"Found {past_due_profiles.count()} past due accounts "
                f"(grace period: {grace_days} days)"
            )

        processed = 0
        for profile in past_due_profiles:
            user = profile.user
            old_tier = profile.account_tier

            # Count surveys that will be closed
            survey_count = (
                Survey.objects.filter(owner=user)
                .exclude(status=Survey.Status.CLOSED)
                .count()
            )
            free_tier_limit = 3
            surveys_to_close = max(0, survey_count - free_tier_limit)

            days_past_due = (now - profile.updated_at).days

            if verbose or dry_run:
                self.stdout.write(
                    f"\n  User: {user.username} ({user.email})"
                    f"\n    Old tier: {old_tier}"
                    f"\n    Days past due: {days_past_due}"
                    f"\n    Surveys to close: {surveys_to_close}"
                )

            if not dry_run:
                # Force downgrade to FREE (this closes excess surveys)
                success, message = profile.force_downgrade_tier(
                    UserProfile.AccountTier.FREE
                )

                if success:
                    # Update subscription status
                    profile.subscription_status = UserProfile.SubscriptionStatus.UNPAID
                    profile.payment_subscription_id = ""
                    profile.save(
                        update_fields=[
                            "subscription_status",
                            "payment_subscription_id",
                            "updated_at",
                        ]
                    )

                    logger.info(
                        f"Past due account downgraded: {user.username} "
                        f"from {old_tier} to FREE after {days_past_due} days, "
                        f"{surveys_to_close} surveys closed"
                    )

                    # Send email notification
                    try:
                        send_subscription_expired_email(
                            user=user,
                            old_tier=old_tier,
                            survey_count=survey_count,
                            surveys_closed=surveys_to_close,
                            reason="payment_failed",
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send past due email to {user.email}: {e}"
                        )

                    self.stdout.write(
                        self.style.SUCCESS(f"    ✓ Downgraded to FREE tier")
                    )
                else:
                    logger.error(f"Failed to downgrade {user.username}: {message}")
                    self.stdout.write(self.style.ERROR(f"    ✗ Failed: {message}"))

            processed += 1

        return processed
