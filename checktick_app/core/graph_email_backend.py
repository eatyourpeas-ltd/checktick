"""Microsoft Graph API email backend for Django.

Uses OAuth2 client credentials flow (modern auth) to send mail via Microsoft 365.
This avoids SMTP AUTH entirely, so Security Defaults can remain enabled on the tenant.

Azure AD setup required (one-time):
1. Azure Portal → Azure Active Directory → App registrations → New registration
2. API permissions → Add → Microsoft Graph → Application permissions → Mail.Send
3. Grant admin consent for your organisation
4. Certificates & secrets → New client secret → copy the value

Required env vars:
    GRAPH_CLIENT_ID      – Application (client) ID from the app registration
    GRAPH_CLIENT_SECRET  – Client secret value
    GRAPH_TENANT_ID      – Directory (tenant) ID (same domain as OIDC_OP_TENANT_ID_AZURE)
    EMAIL_HOST_USER      – The licensed M365 mailbox used as the sending mailbox
                           (must exist as a real mailbox, not just an alias)
    EMAIL_BACKEND        – checktick_app.core.graph_email_backend.GraphEmailBackend
"""

from __future__ import annotations

from email.utils import parseaddr
import logging
import threading
import time

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
import requests

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"

# Simple in-memory token cache (shared across threads, protected by a lock)
_token_cache: dict[str, object] = {"access_token": None, "expires_at": 0.0}
_token_lock = threading.Lock()


def _get_access_token() -> str:
    with _token_lock:
        now = time.monotonic()
        # Reuse existing token if it has more than 60 seconds left
        if _token_cache["access_token"] and now < (_token_cache["expires_at"] - 60):
            return _token_cache["access_token"]  # type: ignore[return-value]

        resp = requests.post(
            _TOKEN_URL.format(tenant_id=settings.GRAPH_TENANT_ID),
            data={
                "grant_type": "client_credentials",
                "client_id": settings.GRAPH_CLIENT_ID,
                "client_secret": settings.GRAPH_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
        _token_cache["access_token"] = token_data["access_token"]
        _token_cache["expires_at"] = now + token_data.get("expires_in", 3600)
        return _token_cache["access_token"]  # type: ignore[return-value]


def _graph_recipient(addr: str) -> dict:
    """Convert a Django address string ('Name <email>' or plain email) to Graph format."""
    name, email = parseaddr(addr)
    entry: dict = {"emailAddress": {"address": email}}
    if name:
        entry["emailAddress"]["name"] = name
    return entry


class GraphEmailBackend(BaseEmailBackend):
    """Django email backend that sends via Microsoft Graph API (modern auth)."""

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0

        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception as exc:
                if not self.fail_silently:
                    raise
                logger.exception("GraphEmailBackend: failed to send email: %s", exc)
        return sent

    def _send(self, message) -> None:
        # Prefer HTML alternative body if present (EmailMultiAlternatives)
        body_content = message.body
        body_content_type = "Text"
        if hasattr(message, "alternatives"):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    body_content = content
                    body_content_type = "Html"
                    break

        graph_message: dict = {
            "subject": message.subject,
            "body": {
                "contentType": body_content_type,
                "content": body_content,
            },
            "toRecipients": [_graph_recipient(addr) for addr in message.to],
        }

        if message.cc:
            graph_message["ccRecipients"] = [_graph_recipient(a) for a in message.cc]
        if message.bcc:
            graph_message["bccRecipients"] = [_graph_recipient(a) for a in message.bcc]
        if message.reply_to:
            graph_message["replyTo"] = [_graph_recipient(a) for a in message.reply_to]

        # The sending mailbox must be a real licensed M365 mailbox.
        # EMAIL_HOST_USER is that mailbox. If the desired from_email is an alias
        # on that mailbox (configured in M365), it will appear as the sender.
        _, sending_mailbox = parseaddr(settings.EMAIL_HOST_USER)

        # Set the display From address if it differs from the mailbox.
        # Requires the mailbox to have "send as" or "send on behalf of" rights
        # for that address in Exchange Online (aliases are fine).
        _, from_addr = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        if from_addr and from_addr != sending_mailbox:
            graph_message["from"] = _graph_recipient(
                message.from_email or settings.DEFAULT_FROM_EMAIL
            )

        payload = {
            "message": graph_message,
            "saveToSentItems": False,
        }

        token = _get_access_token()
        resp = requests.post(
            _SEND_URL.format(sender=sending_mailbox),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=getattr(settings, "EMAIL_TIMEOUT", 10),
        )
        resp.raise_for_status()
