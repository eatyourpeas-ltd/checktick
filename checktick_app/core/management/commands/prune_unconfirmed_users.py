#!/usr/bin/env python3
"""
Django management command to prune users who have not confirmed their email addresses.

This command should be run daily (e.g., via cron or scheduled job) to:
0a. Delete/deactivate unconfirmed users whose signup email HARD-BOUNCED —
    delivery-failure notifications (NDRs) are read back from the M365
    sending mailbox via the Graph API. A hard bounce is the only
    authoritative evidence that a *mailbox* does not exist (the DNS check
    in 0b can only reject undeliverable *domains*). This phase fails
    gracefully: a missing Mail.Read permission (401/403), a network
    outage, or any other error is logged and the rest of the run
    continues. Disable with EMAIL_BOUNCE_PROCESSING_ENABLED=False.
0b. Delete/deactivate unconfirmed users whose signup email domain provably
    cannot receive mail (DNS MX/A check) — the confirmation and warning
    emails could never reach them, so the grace period is skipped
1. Send pre-removal warning emails at 7 days and 1 day before the grace period ends
2. Deactivate existing users whose grace period has expired without confirmation
3. Delete new signups that never confirmed and have no meaningful data

Policy:
- Hard bounces prune immediately, regardless of account age (the remote
  server itself rejected the mailbox). Only explicit permanent 5xx
  failures that are NOT 5.7.x policy/SPF rejections are acted on — see
  email_bounces.py for the classification rules.
- Unconfirmed users whose email domain does not exist or has no mail
  exchanger are pruned on the next run (after a 24h minimum age), without
  waiting out the grace period. Only definitive DNS evidence triggers
  this — resolver timeouts and other lookup failures leave the user in
  the normal warning/grace flow (fail open). Disable with
  EMAIL_VALIDATION_ENABLED=False or --skip-email-validation.
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
    python manage.py prune_unconfirmed_users --skip-email-validation
"""

from datetime import timedelta
from email.utils import parseaddr
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
import requests

from checktick_app.core.account_pruning import (
    get_feature_cutoff_date,
    prune_unconfirmed_user,
)
from checktick_app.core.email_bounces import fetch_bounce_messages
from checktick_app.core.email_utils import send_unconfirmed_account_warning_email
from checktick_app.core.email_validation import check_email_deliverability

logger = logging.getLogger(__name__)

# Default grace period for unconfirmed accounts (days)
DEFAULT_GRACE_DAYS = 30

# Minimum age (hours) before an invalid-email account is pruned, so a
# brand-new domain whose DNS has not fully propagated is never deleted on
# signup day, and the signup flow's own synchronous bounce handling gets
# a chance to run first.
INVALID_EMAIL_MIN_AGE_HOURS = 24

# Default NDR lookback window (hours) for the bounce phase. Read from
# settings EMAIL_BOUNCE_LOOKBACK_HOURS. 7 days matches the daily cadence
# with margin for a missed run; NDRs are re-read harmlessly (idempotent).
BOUNCE_LOOKBACK_HOURS = 168

# Warning windows: (stage_name, days_before_removal).
# Ordered from furthest-out to closest-in so the command can pick the
# most-advanced stage that should have been sent.
WARNING_WINDOWS = [
    ("1week", 7),
    ("1day", 1),
]

# Stage progression order (furthest to closest).
STAGE_ORDER = ["1week", "1day"]

User = get_user_model()


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
        "Prune unconfirmed users: remove accounts whose signup email domain "
        "cannot receive mail, send pre-removal warnings, then deactivate "
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
        parser.add_argument(
            "--skip-email-validation",
            action="store_true",
            help=(
                "Skip the DNS deliverability check on unconfirmed signup "
                "emails (also disabled via EMAIL_VALIDATION_ENABLED=False)"
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        grace_days = options["grace_days"]
        validate_emails = (
            getattr(settings, "EMAIL_VALIDATION_ENABLED", True)
            and not options["skip_email_validation"]
        )

        cutoff = timezone.now() - timedelta(days=grace_days)
        feature_cutoff_date = get_feature_cutoff_date()
        validate_bounces = (
            getattr(settings, "EMAIL_BOUNCE_PROCESSING_ENABLED", True)
            and "graph_email_backend" in settings.EMAIL_BACKEND
        )

        self.stdout.write(
            self.style.SUCCESS(f"Starting unconfirmed user pruning at {timezone.now()}")
        )
        self.stdout.write(f"  Grace period: {grace_days} days")
        self.stdout.write(f"  Feature cutoff: {feature_cutoff_date.date()}")
        self.stdout.write(f"  Email validation: {'on' if validate_emails else 'off'}")
        self.stdout.write(f"  Bounce processing: {'on' if validate_bounces else 'off'}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # --- 0a. Prune unconfirmed users whose signup email hard-bounced ---
        # Reads NDRs from the M365 sending mailbox. Fails gracefully: an
        # outage or missing permission never aborts the prune run.
        bounce_deactivated = 0
        bounce_deleted = 0
        if validate_bounces:
            bounce_deactivated, bounce_deleted = self._prune_bounced_users(
                feature_cutoff_date, dry_run, verbose
            )

        # --- 0b. Prune unconfirmed users whose signup email cannot receive mail ---
        # Runs before the warning phase so accounts with undeliverable
        # domains are removed before any warning email is sent to them.
        invalid_deactivated = 0
        invalid_deleted = 0
        if validate_emails:
            invalid_deactivated, invalid_deleted = self._prune_invalid_email_users(
                feature_cutoff_date, dry_run, verbose
            )

        # --- 1. Send pre-removal warnings to users approaching the cutoff ---
        warnings_sent = self._send_warnings(cutoff, grace_days, dry_run, verbose)

        # --- 2. Prune users past the grace period ---
        deactivated, deleted = self._prune_users(
            cutoff, grace_days, feature_cutoff_date, dry_run, verbose
        )

        self.stdout.write(
            self.style.SUCCESS(f"\nPruning completed at {timezone.now()}")
        )
        if validate_bounces:
            self.stdout.write(
                f"  - Bounce pruned: {bounce_deactivated + bounce_deleted} "
                f"(deactivated: {bounce_deactivated}, deleted: {bounce_deleted})"
            )
        if validate_emails:
            self.stdout.write(
                f"  - Invalid email pruned: {invalid_deactivated + invalid_deleted} "
                f"(deactivated: {invalid_deactivated}, deleted: {invalid_deleted})"
            )
        self.stdout.write(f"  - Warnings sent: {warnings_sent}")
        self.stdout.write(f"  - Deactivated:   {deactivated}")
        self.stdout.write(f"  - Deleted:       {deleted}")

    def _prune_bounced_users(self, feature_cutoff_date, dry_run, verbose):
        """0a: prune unconfirmed accounts whose signup email hard-bounced.

        Reads delivery-failure notifications from the M365 sending mailbox
        (EMAIL_HOST_USER) via the Graph API — see email_bounces.py for the
        fetch/classification details. Only hard bounces (explicit permanent
        5xx, excluding 5.7.x policy rejections) prune, and only unconfirmed,
        active, non-privileged accounts (no minimum age: the receiving server
        itself rejected the mailbox, so the evidence is immediate).

        This phase NEVER aborts the prune run: a missing Mail.Read permission
        (401/403), a network outage, or any unexpected error is logged and
        the remaining phases continue without bounce evidence.
        """
        mailbox = parseaddr(settings.EMAIL_HOST_USER)[1]
        if not mailbox:
            logger.error(
                "EMAIL_HOST_USER is not set — cannot read bounces from the "
                "sending mailbox. Skipping bounce processing."
            )
            self.stdout.write(
                self.style.WARNING(
                    "  EMAIL_HOST_USER is not set — bounce processing skipped."
                )
            )
            return 0, 0

        lookback_hours = getattr(
            settings, "EMAIL_BOUNCE_LOOKBACK_HOURS", BOUNCE_LOOKBACK_HOURS
        )
        self.stdout.write(
            f"\nReading bounces from mailbox {mailbox} " f"(lookback {lookback_hours}h)"
        )

        try:
            bounces = fetch_bounce_messages(mailbox, lookback_hours)
        except requests.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403):
                logger.error(
                    "Graph API rejected the mailbox read (%s) — the Mail.Read "
                    "application permission (with admin consent) is probably "
                    "missing on the Azure app registration used for sending. "
                    "Skipping bounce processing; the rest of the prune run "
                    "continues.",
                    status,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"  Bounce read rejected by Graph ({status}) — grant the "
                        "Mail.Read application permission (admin consent) on the "
                        "Azure app registration used for sending. Continuing "
                        "without bounce processing."
                    )
                )
            else:
                logger.error(
                    "Graph API error while reading bounces (%s). Skipping bounce "
                    "processing; the rest of the prune run continues.",
                    exc,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"  Graph API error while reading bounces ({exc}). "
                        "Continuing without bounce processing."
                    )
                )
            return 0, 0
        except requests.RequestException as exc:
            # Network outage, DNS failure, timeout — never abort the run.
            logger.error(
                "Network error while reading bounces from the sending mailbox: "
                "%s. Skipping bounce processing; the rest of the prune run "
                "continues.",
                exc,
            )
            self.stdout.write(
                self.style.WARNING(
                    f"  Network error while reading bounces ({exc}). "
                    "Continuing without bounce processing."
                )
            )
            return 0, 0
        except Exception:
            # Anything else must never abort the daily prune.
            logger.exception(
                "Unexpected error while reading bounces. Skipping bounce "
                "processing; the rest of the prune run continues."
            )
            self.stdout.write(
                self.style.WARNING(
                    "  Unexpected error while reading bounces. "
                    "Continuing without bounce processing."
                )
            )
            return 0, 0

        hard = [b for b in bounces if b.is_hard]
        self.stdout.write(
            f"Found {len(bounces)} bounce(s) in the lookback window "
            f"({len(hard)} hard)"
        )

        deactivated = 0
        deleted = 0
        seen: set[str] = set()

        for bounce in bounces:
            if verbose:
                self.stdout.write(
                    f"\n  Bounce: {bounce.recipient} ({bounce.classification})"
                    f"\n    Subject: {bounce.subject}"
                    f"\n    Received: {bounce.received_at}"
                    f"\n    Status: {bounce.status_code}"
                )

            if not bounce.is_hard:
                if verbose:
                    self.stdout.write("    Soft/unknown bounce — no action (fail open)")
                continue

            if not bounce.recipient:
                if verbose:
                    self.stdout.write("    No recipient parsed — skipping")
                continue

            if bounce.recipient.lower() in seen:
                continue  # Multiple NDRs for the same address
            seen.add(bounce.recipient.lower())

            # Only unconfirmed, active, non-privileged accounts are pruned
            # on bounce evidence. Same exclusions as the grace-period phase.
            candidates = (
                User.objects.filter(
                    email__iexact=bounce.recipient,
                    profile__email_confirmed=False,
                    is_active=True,
                )
                .exclude(is_superuser=True)
                .exclude(is_staff=True)
                .exclude(oidc__email_verified=True)
                .select_related("profile")
            )

            if not candidates.exists():
                self._report_non_prunable_bounce(bounce)
                continue

            for user in candidates:
                action = prune_unconfirmed_user(
                    user,
                    feature_cutoff_date=feature_cutoff_date,
                    reason="email_bounced",
                    detail=(f"signup email hard-bounced (status {bounce.status_code})"),
                    metadata_extra={
                        "bounce_subject": bounce.subject,
                        "bounce_received_at": bounce.received_at,
                        "bounce_status": bounce.status_code,
                    },
                    dry_run=dry_run,
                    verbose=verbose,
                    stdout=self.stdout,
                    style=self.style,
                )
                if action == "deactivated":
                    deactivated += 1
                else:
                    deleted += 1

        return deactivated, deleted

    def _report_non_prunable_bounce(self, bounce):
        """Report a hard bounce that has no prunable target account."""
        recipient = bounce.recipient or "(unparsed recipient)"
        confirmed = User.objects.filter(
            email__iexact=recipient, is_active=True, profile__email_confirmed=True
        ).exists()
        if confirmed:
            # The account is confirmed but its mailbox now rejects mail —
            # password resets and survey invitations will not arrive.
            logger.warning(
                "Hard bounce for confirmed account: %s (status %s) — account left "
                "active, but it can no longer receive email such as password resets",
                recipient,
                bounce.status_code,
                extra={
                    "recipient": recipient,
                    "bounce_status": bounce.status_code,
                },
            )
            self.stdout.write(
                self.style.WARNING(
                    f"    Hard bounce for CONFIRMED account {recipient} — "
                    "no action taken, but the account cannot receive email "
                    "(password resets will bounce)."
                )
            )
        else:
            logger.info(
                "Hard bounce for address with no active account: %s",
                recipient,
            )
            self.stdout.write(
                f"    No unconfirmed account found for {recipient} — nothing to do."
            )

    def _prune_invalid_email_users(self, feature_cutoff_date, dry_run, verbose):
        """Deactivate/delete unconfirmed users whose signup email is undeliverable.

        The confirmation email (and any warning email) can never reach
        these accounts, so waiting out the grace period serves no purpose.
        Only definitive DNS evidence (domain does not exist, or has no MX
        and no address record) triggers removal — timeouts and resolver
        errors leave the user in the normal warning/grace flow.
        """
        min_age = timezone.now() - timedelta(hours=INVALID_EMAIL_MIN_AGE_HOURS)
        candidates = (
            User.objects.filter(
                profile__email_confirmed=False,
                is_active=True,
                date_joined__lt=min_age,
            )
            .exclude(is_superuser=True)
            .exclude(is_staff=True)
            # Same OIDC exemption as the warning window — see comment there.
            .exclude(oidc__email_verified=True)
            .select_related("profile")
        )

        if verbose:
            self.stdout.write(
                f"\nFound {candidates.count()} unconfirmed users for email validation"
            )

        deactivated = 0
        deleted = 0

        for user in candidates:
            try:
                result = check_email_deliverability(user.email)
            except Exception:
                # A DNS failure must never cost a user their account.
                logger.exception(
                    "Email deliverability check failed for user %s",
                    user.username,
                )
                continue

            if not result.is_invalid:
                if verbose:
                    self.stdout.write(
                        f"  Email {result.status}: {user.username} ({user.email})"
                    )
                continue

            action = prune_unconfirmed_user(
                user,
                feature_cutoff_date=feature_cutoff_date,
                reason="invalid_signup_email",
                detail=f"invalid signup email ({result.reason})",
                metadata_extra={
                    "email_domain": user.email.rsplit("@", 1)[-1].lower(),
                    "dns_reason": result.reason,
                },
                dry_run=dry_run,
                verbose=verbose,
                stdout=self.stdout,
                style=self.style,
            )
            if action == "deactivated":
                deactivated += 1
            else:
                deleted += 1

        return deactivated, deleted

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
            # OIDC users never receive a confirmation link — their email is
            # verified by their provider and email_confirmed_required exempts
            # them. The backend syncs profile.email_confirmed on login, but
            # this exclusion also protects users who have not logged in since
            # that sync shipped (otherwise every OIDC account would be
            # deactivated/deleted after the grace period).
            .exclude(oidc__email_verified=True)
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
            # Same OIDC exemption as the warning window — see comment there.
            .exclude(oidc__email_verified=True)
            .select_related("profile")
        )

        if verbose:
            self.stdout.write(
                f"\nFound {unconfirmed_users.count()} unconfirmed users past grace period"
            )

        deactivated = 0
        deleted = 0

        for user in unconfirmed_users:
            action = prune_unconfirmed_user(
                user,
                feature_cutoff_date=feature_cutoff_date,
                reason="unconfirmed_email",
                detail=f"unconfirmed email after {grace_days} days",
                metadata_extra={"grace_days": grace_days},
                dry_run=dry_run,
                verbose=verbose,
                stdout=self.stdout,
                style=self.style,
            )
            if action == "deactivated":
                deactivated += 1
            else:
                deleted += 1

        return deactivated, deleted
