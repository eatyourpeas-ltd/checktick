"""Fetch and parse bounce (NDR) messages from the M365 sending mailbox.

A hard bounce (a "delivery failed permanently" NDR) is the only
authoritative signal that a signup email's *mailbox* does not exist.
The DNS checks in ``email_validation.py`` can only prove things about
the *domain*; only the receiving mail server's own rejection proves the
mailbox is invalid.

The Microsoft Graph ``sendMail`` API used by ``graph_email_backend``
accepts mail to any address and bounces asynchronously, so the signup
flow can never see the failure. NDRs are delivered back to the sending
mailbox (``EMAIL_HOST_USER``), which this module reads via the Graph
``mailFolders/{folder}/messages`` endpoint. It requires the ``Mail.Read``
application permission (admin consent) on the same Azure app registration
used for sending. Because Mail.Read is an application permission that
grants access to ALL mailboxes in the tenant, scope it to just the
sending mailbox with an Exchange Online ApplicationAccessPolicy.

This runs as a phase of the daily ``prune_unconfirmed_users`` cron (see
``management/commands/prune_unconfirmed_users.py``) — there is no
separate cron job. The phase fails gracefully: a missing Mail.Read
permission (401/403), a network outage, or any other error is logged and
the rest of the prune run continues.

Only unconfirmed, active, non-privileged accounts are ever pruned on
bounce evidence (see ``account_pruning.prune_unconfirmed_user``). A hard
bounce for a confirmed account is logged as a warning — the account can
no longer receive password resets — but the account is left alone.

Classification is deliberately conservative — only an explicit permanent
failure status (5xx) that is NOT a policy rejection prunes:

* 5.7.x (policy/spam/block, including 5.7.26 SPF failures) is UNKNOWN —
  the mailbox may exist and OUR mail may be the problem. Pruning every
  unconfirmed signup because CheckTick's own SPF/DKIM is misconfigured
  would delete real users.
* An "Undeliverable" subject with no diagnostic status is UNKNOWN — some
  gateways use that wording for policy bounces.
* 4xx (temporary: greylisting, full mailbox) is SOFT — never pruned.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from email.utils import parseaddr
import logging
import re

from django.conf import settings
from django.utils import timezone
import requests

from .graph_email_backend import _get_access_token

logger = logging.getLogger(__name__)

# Classification of a parsed bounce.
HARD = "hard"  # permanent failure — the mailbox does not exist / refused
SOFT = "soft"  # temporary failure — greylisting, full mailbox, delayed
UNKNOWN = "unknown"  # cannot tell — never act on this

# Graph endpoint for messages in the mailbox Inbox. NDRs are delivered
# there like any other inbound mail.
_GRAPH_MESSAGES_URL = (
    "https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders/Inbox/messages"
)

# Safety cap on messages examined per run (pagination limit). The sending
# mailbox should only contain bounces and the odd auto-reply; this bound
# exists so a flooded mailbox cannot wedge the cron.
MAX_MESSAGES_PER_RUN = 500

_PAGE_SIZE = 50

# Subjects Exchange Online uses for delivery-status notifications.
# Language-dependent in principle, but the M365 tenant's NDR language
# matches the tenant locale; these are the en-GB/en-US forms.
_NDR_SUBJECT_PREFIXES = (
    "undeliverable",
    "delivery status notification",
    "delivery has failed",
    "returned mail",
    "mail delivery failed",
)

# RFC 3464 report headers, present in the NDR text when the reporting
# MTA includes the delivery-status part.
_FINAL_RECIPIENT_RE = re.compile(
    r"Final-Recipient:\s*rfc822;\s*([^\s;]+)", re.IGNORECASE
)

# Exchange Online's human-readable failure block:
#   "Delivery has failed to these recipients or groups:\n\n<address>..."
_FAILED_RECIPIENTS_RE = re.compile(
    r"Delivery has failed to these recipients or groups:?\s*[\r\n]+([^\r\n]+)",
    re.IGNORECASE,
)

# Enhanced status codes: "Remote Server returned '550 5.4.1 ...'" or a
# bare "550 5.4.1" in the diagnostic block.
_ENHANCED_STATUS_RE = re.compile(r"\b([45])\d{2}[ \t]+(\d\.\d{1,3}\.\d{1,3})")

# RFC 3464 "Status: 5.1.1" line.
_STATUS_LINE_RE = re.compile(r"Status:\s*([45]\.\d{1,3}\.\d{1,3})", re.IGNORECASE)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass(frozen=True)
class BounceMessage:
    """One parsed delivery-status notification."""

    message_id: str
    subject: str
    received_at: str
    recipient: str | None
    classification: str
    status_code: str | None

    @property
    def is_hard(self) -> bool:
        return self.classification == HARD


def fetch_bounce_messages(
    mailbox: str,
    lookback_hours: int,
    *,
    max_messages: int = MAX_MESSAGES_PER_RUN,
    request_timeout: int = 30,
) -> list[BounceMessage]:
    """List recent Inbox NDRs from the sending mailbox, parsed.

    Raises ``requests.HTTPError`` on Graph API failure (including 401/403
    when the Mail.Read application permission is missing — callers should
    surface that as actionable guidance).
    """
    token = _get_access_token()
    start = (timezone.now() - timedelta(hours=lookback_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    url = _GRAPH_MESSAGES_URL.format(mailbox=mailbox)
    params = {
        "$filter": f"receivedDateTime ge {start}",
        "$orderby": "receivedDateTime desc",
        "$top": str(_PAGE_SIZE),
        "$select": "id,subject,receivedDateTime,from,body",
    }
    # Ask Graph for plain-text bodies so no HTML parsing is needed.
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.body-content-type="text"',
    }

    bounces: list[BounceMessage] = []
    fetched = 0

    while url and fetched < max_messages:
        resp = requests.get(
            url,
            params=params if fetched == 0 else None,
            headers=headers,
            timeout=request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        for message in data.get("value", []):
            fetched += 1
            parsed = _parse_message(message)
            if parsed is not None:
                bounces.append(parsed)

        # nextLink already carries the $skip paging parameters.
        url = data.get("@odata.nextLink")
        params = None

    return bounces


def _parse_message(message: dict) -> BounceMessage | None:
    """Parse one Graph message object, or None if it is not an NDR."""
    subject = message.get("subject") or ""
    sender = ""
    from_block = message.get("from") or {}
    sender = (from_block.get("emailAddress") or {}).get("address") or ""

    if not _looks_like_ndr(subject, sender):
        return None

    body = (message.get("body") or {}).get("content") or ""
    recipient, classification, status_code = parse_bounce(subject, body)

    return BounceMessage(
        message_id=message.get("id") or "",
        subject=subject,
        received_at=message.get("receivedDateTime") or "",
        recipient=recipient,
        classification=classification,
        status_code=status_code,
    )


def _looks_like_ndr(subject: str, sender: str) -> bool:
    """Heuristic: is this message a delivery-status notification?"""
    lowered = subject.strip().lower()
    if any(lowered.startswith(p) for p in _NDR_SUBJECT_PREFIXES):
        return True
    local_part = parseaddr(sender)[1].split("@", 1)[0].lower()
    return local_part.startswith(("postmaster", "mailer-daemon", "microsoftexchange"))


def parse_bounce(subject: str, body: str) -> tuple[str | None, str, str | None]:
    """Extract (recipient, classification, status_code) from an NDR.

    Pure function — everything else is a thin wrapper around this, which
    keeps the parsing independently testable.

    Recipient extraction order:
    1. Exchange Online's "Delivery has failed to these recipients or
       groups:" block (first email on the following line)
    2. RFC 3464 ``Final-Recipient: rfc822;`` header

    Classification (conservative — see module docstring):
    * 4xx status (``452 4.2.2``) = soft (temporary — greylisting, full mailbox)
    * "Delayed"/"Delay" subject with no status = soft
    * 5xx status that is NOT 5.7.x policy = hard (the mailbox does not exist)
    * 5.7.x policy/spam/SPF rejections = unknown — the mailbox may exist;
      our own mail may be the problem, so this is never pruned
    * "Undeliverable" subject with no diagnostic status = unknown — the
      wording is also used by policy gateways
    * anything else = unknown — never acted on
    """
    recipient = _extract_recipient(body)
    status_code, first_digit, enhanced_class = _extract_status(body)

    if status_code is None:
        if "delay" in subject.strip().lower():
            return recipient, SOFT, None
        return recipient, UNKNOWN, None

    if first_digit == "4":
        return recipient, SOFT, status_code

    if enhanced_class and enhanced_class.startswith("5.7."):
        # Policy/spam/block rejection (incl. 5.7.26 SPF failure). The
        # mailbox may well exist — never prune on this evidence.
        return recipient, UNKNOWN, status_code

    return recipient, HARD, status_code


def _extract_recipient(body: str) -> str | None:
    """Pull the bounced recipient address out of the NDR body."""
    # Exclude our own addresses — the "Original message headers" section
    # quotes From: us, and a mis-parse must never prune a colleague.
    own = {getattr(settings, "DEFAULT_FROM_EMAIL", "").lower()} | {
        parseaddr(getattr(settings, "EMAIL_HOST_USER", ""))[1].lower()
    }

    match = _FAILED_RECIPIENTS_RE.search(body)
    if match:
        email_match = _EMAIL_RE.search(match.group(1))
        if email_match:
            candidate = email_match.group(0).lower()
            if candidate not in own:
                return candidate

    match = _FINAL_RECIPIENT_RE.search(body)
    if match:
        candidate = match.group(1).strip().strip("<>").lower()
        if candidate not in own:
            return candidate

    return None


def _extract_status(body: str) -> tuple[str | None, str | None, str | None]:
    """Return (status_text, first_digit, enhanced_class) or (None, None, None).

    ``status_text`` is for audit output only; classification uses
    ``first_digit`` and the 5.7.x check on ``enhanced_class``.
    """
    match = _ENHANCED_STATUS_RE.search(body)
    if match:
        enhanced = match.group(2)
        return match.group(0).strip(), match.group(1), enhanced
    match = _STATUS_LINE_RE.search(body)
    if match:
        enhanced = match.group(1)
        return enhanced, enhanced[0], enhanced
    return None, None, None
