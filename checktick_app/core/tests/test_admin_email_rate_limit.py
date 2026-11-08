"""Tests for the admin error-email rate-limit filter.

The filter exists because AdminEmailHandler emails on every ERROR record
with no throttle (found live 2026-11-08: a cilium-operator lease thrash
blipped in-cluster DNS every few minutes and each blip emailed the
admins). See docs/civo-kubernetes-operations.md open item 5.
"""

import logging
import time

import pytest

from checktick_app.core.logging.admin_email_rate_limit import (
    AdminEmailRateLimitFilter,
)


def _record() -> logging.LogRecord:
    return logging.LogRecord(
        name="django.request",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Service Unavailable: /healthz",
        args=(),
        exc_info=None,
    )


@pytest.fixture(autouse=True)
def _reset_window():
    """Isolate the class-level window state between tests."""
    AdminEmailRateLimitFilter._last_sent = None
    yield
    AdminEmailRateLimitFilter._last_sent = None


class TestAdminEmailRateLimitFilter:
    def test_first_record_passes(self, settings):
        """The first ERROR in a window is always delivered."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 900
        assert AdminEmailRateLimitFilter().filter(_record()) is True

    def test_second_record_within_window_dropped(self, settings):
        """A second ERROR inside the window is suppressed."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 900
        flt = AdminEmailRateLimitFilter()
        assert flt.filter(_record()) is True
        assert flt.filter(_record()) is False

    def test_record_after_window_passes(self, settings):
        """Once the window elapses, the next ERROR is delivered."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 60
        flt = AdminEmailRateLimitFilter()
        assert flt.filter(_record()) is True
        # Simulate the window elapsing.
        AdminEmailRateLimitFilter._last_sent = time.monotonic() - 61
        assert flt.filter(_record()) is True

    def test_zero_disables_limit(self, settings):
        """ADMIN_EMAIL_RATE_LIMIT_SECONDS=0 turns the throttle off."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 0
        flt = AdminEmailRateLimitFilter()
        assert flt.filter(_record()) is True
        assert flt.filter(_record()) is True

    def test_window_shared_across_instances(self, settings):
        """One window per process, not per filter instance."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 900
        assert AdminEmailRateLimitFilter().filter(_record()) is True
        assert AdminEmailRateLimitFilter().filter(_record()) is False

    def test_first_record_passes_on_fresh_boot_clock(self, settings, monkeypatch):
        """Regression: a fresh machine's monotonic clock can read BELOW
        the window (CI runners boot minutes before the tests) — the first
        record must still pass (found in CI 2026-11-08)."""
        settings.ADMIN_EMAIL_RATE_LIMIT_SECONDS = 900
        monkeypatch.setattr(
            "checktick_app.core.logging.admin_email_rate_limit.time.monotonic",
            lambda: 60.0,
        )
        assert AdminEmailRateLimitFilter().filter(_record()) is True
        assert AdminEmailRateLimitFilter().filter(_record()) is False
