"""Rate-limit Django admin error emails (ops open item 5).

``AdminEmailHandler`` sends one email per ERROR log record with no built-in
throttling: a transient outage turns into an outbound email storm that
amplifies load and buries real alerts. Found live 2026-11-08 — the
cilium-operator lease thrash on the Civo cluster blipped in-cluster DNS
for seconds at a time every few minutes, and each blip produced a fresh
healthz ERROR email to the admins.

This filter allows at most one admin email per window (default 15 min,
``ADMIN_EMAIL_RATE_LIMIT_SECONDS``; ``0`` disables the limit). Dropped
records still reach every other handler (console → stdout → OpenObserve),
so nothing is lost — only the duplicate emails are suppressed.
"""

import logging
import time

from django.conf import settings


class AdminEmailRateLimitFilter(logging.Filter):
    """Pass the first ERROR record in each window, drop the rest.

    The window state is class-level on purpose: one shared window per
    process across every handler that mounts this filter. Gunicorn
    workers each get their own window, bounding a storm at one email
    per worker per window instead of one email per ERROR record.
    """

    _last_sent: float = 0.0

    def filter(self, record: logging.LogRecord) -> bool:
        window = getattr(settings, "ADMIN_EMAIL_RATE_LIMIT_SECONDS", 900)
        if window <= 0:
            return True
        now = time.monotonic()
        if now - type(self)._last_sent >= window:
            type(self)._last_sent = now
            return True
        return False
