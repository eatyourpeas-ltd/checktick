#!/usr/bin/env python3
"""Send pre-expiry warning emails for time-limited subscriptions.

Runs daily (alongside ``process_expired_subscriptions``) and sends warning
emails at three windows before a subscription's ``subscription_current_period_end``:

1. **1 month** before (30 days)
2. **1 week** before (7 days)
3. **1 day** before (1 day)

Idempotency is enforced via ``UserProfile.last_expiry_warning_stage``, which
records the most recent stage sent (``"1month"``, ``"1week"``, ``"1day"``).
Each stage is sent at most once per expiry cycle. When the subscription is
renewed or extended, the caller should clear both
``last_expiry_warning_stage`` and ``last_expiry_warning_sent_at`` so the
warnings restart for the new expiry date.

Only profiles with:
- ``subscription_current_period_end`` set and in the future
- ``subscription_status`` in ``[ACTIVE, CANCELED]`` (canceled-but-still-active
  is the GoCardless "cancel at period end" state)
- ``account_tier != FREE``

are considered. Self-hosted deployments are skipped (no billing).

Usage:
    python manage.py process_expiring_subscriptions
    python manage.py process_expiring_subscriptions --dry-run
    python manage.py process_expiring_subscriptions --verbose
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from checktick_app.core.email_utils import send_subscription_expiring_email
from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import Survey

logger = logging.getLogger(__name__)

# Warning windows: (stage_name, days_before_expiry).
# Ordered from furthest-out to closest-in so the command can pick the
# most-advanced stage that should have been sent.
WARNING_WINDOWS = [
    ("1month", 30),
    ("1week", 7),
    ("1day", 1),
]

# Maps stage name -> the set of stages that should already have been sent
# before this stage fires. Used to skip a stage if an earlier one was never
# sent (e.g. user was created 10 days before expiry, so 1month is skipped
# but 1week and 1day still fire).
STAGE_ORDER = ["1month", "1week", "1day"]


class Command(BaseCommand):
    help = (
        "Send pre-expiry warning emails (1 month, 1 week, 1 day before "
        "subscription_current_period_end) for time-limited subscriptions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without sending emails.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed output per profile.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting pre-expiry warning processing at {timezone.now()}"
            )
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - no emails will be sent")
            )

        if getattr(settings, "SELF_HOSTED", False):
            self.stdout.write(
                self.style.WARNING("Self-hosted mode - billing is disabled, skipping")
            )
            return

        now = timezone.now()
        sent_count = 0
        skipped_count = 0

        # Consider all profiles with a future period end and a paid tier.
        # We don't filter by status here because both ACTIVE and CANCELED
        # (cancel-at-period-end) should get warnings.
        candidates = UserProfile.objects.filter(
            subscription_current_period_end__gt=now,
        ).exclude(account_tier=UserProfile.AccountTier.FREE)

        if verbose:
            self.stdout.write(f"Found {candidates.count()} candidate profiles")

        for profile in candidates:
            days_until = (profile.subscription_current_period_end - now).days
            current_stage = profile.last_expiry_warning_stage

            # Determine which stage should fire now.
            stage_to_send = self._stage_to_send(days_until, current_stage)

            if stage_to_send is None:
                skipped_count += 1
                if verbose:
                    self.stdout.write(
                        f"  Skip {profile.user.email}: days_until={days_until}, "
                        f"current_stage={current_stage!r}"
                    )
                continue

            if verbose or dry_run:
                self.stdout.write(
                    f"  {profile.user.email}: days_until={days_until}, "
                    f"sending stage={stage_to_send}"
                )

            if dry_run:
                sent_count += 1
                continue

            # Compute surveys that would be closed on downgrade for the email.
            survey_count = (
                Survey.objects.filter(owner=profile.user)
                .exclude(status=Survey.Status.CLOSED)
                .count()
            )
            free_tier_limit = 3
            surveys_to_close = max(0, survey_count - free_tier_limit)

            try:
                send_subscription_expiring_email(
                    user=profile.user,
                    tier=profile.account_tier,
                    expiry_date=profile.subscription_current_period_end,
                    days_until_expiry=days_until,
                    survey_count=survey_count,
                    surveys_to_close=surveys_to_close,
                    free_tier_limit=free_tier_limit,
                )
                profile.last_expiry_warning_sent_at = now
                profile.last_expiry_warning_stage = stage_to_send
                profile.save(
                    update_fields=[
                        "last_expiry_warning_sent_at",
                        "last_expiry_warning_stage",
                        "updated_at",
                    ]
                )
                sent_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to send pre-expiry warning to "
                    f"{profile.user.email}: {e}"
                )
                self.stdout.write(
                    self.style.ERROR(f"    Failed for {profile.user.email}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"\nPre-expiry processing completed at {timezone.now()}")
        )
        self.stdout.write(f"  - Warnings sent: {sent_count}")
        self.stdout.write(
            f"  - Skipped (already sent or out of window): {skipped_count}"
        )

    def _stage_to_send(self, days_until: int, current_stage: str) -> str | None:
        """Determine which warning stage should fire, if any.

        Returns the stage name to send, or None if no stage should fire now.

        Logic:
        - For each stage from closest-in (1day) to furthest-out (1month),
          check if we're within that window. The closest applicable stage
          wins (so if we're 3 days out, we send 1week, not 1month).
        - Skip if that stage was already sent.
        - Skip a stage if a later (closer) stage was already sent (e.g.
          if 1week was sent, don't send 1month even if we're within 30 days).
        """
        if current_stage:
            try:
                current_idx = STAGE_ORDER.index(current_stage)
            except ValueError:
                current_idx = -1
        else:
            current_idx = -1

        # Walk from closest-in (1day) to furthest-out (1month).
        # The first stage we're within the window for AND haven't already
        # sent (and haven't sent a later stage) is the one to send.
        for idx, (stage_name, days_before) in enumerate(reversed(WARNING_WINDOWS)):
            # reversed() gives 1day, 1week, 1month — i.e. idx 0=1day, 1=1week, 2=1month.
            # Map to STAGE_ORDER index: 1day=2, 1week=1, 1month=0.
            stage_order_idx = len(STAGE_ORDER) - 1 - idx
            if days_until <= days_before:
                # We're within this window. Check we haven't already sent
                # this stage or a later (closer-in) stage.
                if current_idx >= stage_order_idx:
                    continue
                return stage_name
        return None
