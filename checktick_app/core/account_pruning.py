"""Shared deactivate-or-delete policy for unconfirmed-account pruning.

Used by every phase of the ``prune_unconfirmed_users`` cron (grace-period
expiry, DNS deliverability, and hard-bounce NDRs). The policy is identical
in every case:

* existing users (joined before the email confirmation feature) and users
  with meaningful data are deactivated so data and audit trails survive;
* new signups with no meaningful data are deleted outright.

Every action is written to ``AuditLog`` with the caller's ``reason``.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from checktick_app.surveys.models import AuditLog

logger = logging.getLogger(__name__)

# Users created before this date are treated as "existing" (pre-feature).
# This is set to the deployment date of the email confirmation feature.
# Adjust this constant when deploying to production.
#
# NOTE: this default is a constant, not evaluated at import time against
# settings — the effective cutoff is read from settings by callers so that
# EMAIL_CONFIRMATION_CUTOFF overrides (and test isolation) work reliably.
DEFAULT_FEATURE_CUTOFF_DATE = timezone.make_aware(timezone.datetime(2025, 6, 25))


def user_has_meaningful_data(user) -> bool:
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


def get_feature_cutoff_date():
    """Return the effective existing/new-signup cutoff date."""
    return getattr(
        settings,
        "EMAIL_CONFIRMATION_CUTOFF",
        DEFAULT_FEATURE_CUTOFF_DATE,
    )


def prune_unconfirmed_user(
    user,
    *,
    reason: str,
    detail: str,
    metadata_extra: dict | None = None,
    feature_cutoff_date=None,
    dry_run: bool = False,
    verbose: bool = False,
    stdout=None,
    style=None,
) -> str:
    """Apply the shared deactivate-or-delete policy to one unconfirmed user.

    Returns "deactivated" or "deleted" (under dry-run, the would-be action).

    Args:
        reason: audit metadata reason (e.g. "unconfirmed_email",
            "invalid_signup_email", "email_bounced").
        detail: human-readable one-liner for verbose/dry-run output and
            the audit log message.
        metadata_extra: extra audit metadata (bounce/DNS evidence etc).
        feature_cutoff_date: the existing/new-signup cutoff; defaults to
            ``get_feature_cutoff_date()``.
        stdout: an output writer (``BaseCommand.stdout``) for progress
            lines; None disables output.
        style: ``BaseCommand.style`` for coloured output; None = plain.
    """
    if feature_cutoff_date is None:
        feature_cutoff_date = get_feature_cutoff_date()

    is_existing_user = user.date_joined < feature_cutoff_date
    has_data = user_has_meaningful_data(user)
    deactivate = is_existing_user or has_data
    action = "DEACTIVATE" if deactivate else "DELETE"

    if verbose or dry_run:
        if stdout is not None:
            stdout.write(
                f"\n  User: {user.username} ({user.email})"
                f"\n    Reason: {detail}"
                f"\n    Joined: {user.date_joined.date()}"
                f"\n    Existing user: {is_existing_user}"
                f"\n    Has data: {has_data}"
                f"\n    Action: {action}"
            )

    if dry_run:
        return action.lower()

    metadata = {
        "reason": reason,
        "date_joined": user.date_joined.isoformat(),
        "is_existing_user": is_existing_user,
        "has_data": has_data,
        **(metadata_extra or {}),
    }

    if deactivate:
        # Deactivate: preserve data and audit trail
        user.is_active = False
        user.save(update_fields=["is_active"])

        AuditLog.log_security_event(
            action=AuditLog.Action.USER_DEACTIVATED,
            actor=None,
            message=f"User {user.username} ({user.email}) deactivated due to {detail}.",
            severity=AuditLog.Severity.WARNING,
            metadata=metadata,
            target_user=user,
        )
        logger.info("Deactivated unconfirmed user: %s (%s)", user.username, user.email)
        if stdout is not None:
            line = f"    Deactivated: {user.username}"
            stdout.write(style.WARNING(line) if style else line)
        return "deactivated"

    # Delete: new signup with no meaningful data
    email = user.email
    username = user.username
    metadata["email"] = email

    with transaction.atomic():
        AuditLog.log_security_event(
            action=AuditLog.Action.USER_DELETED,
            actor=None,
            message=f"User {username} ({email}) deleted due to {detail}.",
            severity=AuditLog.Severity.INFO,
            metadata=metadata,
            target_user=None,  # User is about to be deleted
        )
        user.delete()

    logger.info("Deleted unconfirmed user: %s (%s)", username, email)
    if stdout is not None:
        line = f"    Deleted: {username}"
        stdout.write(style.ERROR(line) if style else line)
    return "deleted"
