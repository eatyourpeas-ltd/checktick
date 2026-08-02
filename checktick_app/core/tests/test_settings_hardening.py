"""
Tests for production settings hardening (security-review F3, August 2026).

F3 noted that ``SECRET_KEY = env("SECRET_KEY") or os.urandom(32)`` silently
fell back to a per-worker random key when ``SECRET_KEY`` was unset in
production. Each gunicorn worker (and each process restart) derived a
different key, so sessions, CSRF tokens, signed cookies, and password-reset /
email-confirmation tokens broke intermittently across workers, and the
misconfiguration was invisible — no log entry, no raised exception.

The fix fails fast: if ``ENVIRONMENT=production`` and ``SECRET_KEY`` is unset
(or empty), importing settings raises ``ImproperlyConfigured``. The random
fallback is retained for dev only.
"""

from __future__ import annotations

import importlib
import sys

from django.core.exceptions import ImproperlyConfigured
import pytest


def test_secret_key_unset_in_production_raises(monkeypatch):
    """If ENVIRONMENT=production and SECRET_KEY is unset/empty, settings
    import must raise ImproperlyConfigured.

    Pre-fix: ``SECRET_KEY = env("SECRET_KEY") or os.urandom(32)`` silently
    fell back to a per-worker random key, breaking sessions/CSRF/reset tokens
    across workers with no log entry or exception.
    """
    # Simulate a production deploy where SECRET_KEY was never set. We set it
    # to an empty string rather than deleting it because ``environ.Env.read_env``
    # uses ``os.environ.setdefault`` — a deleted key would be re-populated from
    # the project ``.env`` file on settings reload, masking the misconfiguration
    # we are trying to reproduce. An empty string is present (so ``setdefault``
    # leaves it alone) but falsy, which is exactly the misconfigured state.
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "production")

    mod_name = "checktick_app.settings"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module(mod_name)

    # Restore the real settings module so subsequent tests in the same process
    # see the production config again.
    if mod_name in sys.modules:
        del sys.modules[mod_name]


def test_secret_key_set_in_production_does_not_raise(monkeypatch):
    """A correctly-configured production deploy (SECRET_KEY set) must import
    settings without error."""
    monkeypatch.setenv("SECRET_KEY", "a-real-production-secret-key-for-tests")
    monkeypatch.setenv("ENVIRONMENT", "production")

    mod_name = "checktick_app.settings"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    try:
        mod = importlib.import_module(mod_name)
        assert mod.SECRET_KEY == "a-real-production-secret-key-for-tests"
        assert mod.ENVIRONMENT == "production"
    finally:
        # Always restore the real settings module afterwards.
        if mod_name in sys.modules:
            del sys.modules[mod_name]


def test_secret_key_fallback_allowed_in_development(monkeypatch):
    """In development, an unset SECRET_KEY must NOT raise — the random
    fallback is retained for dev convenience."""
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "development")

    mod_name = "checktick_app.settings"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    try:
        mod = importlib.import_module(mod_name)
        # Fallback is a hex string (os.urandom(32).hex()), non-empty.
        assert mod.SECRET_KEY
        assert isinstance(mod.SECRET_KEY, str)
    finally:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
