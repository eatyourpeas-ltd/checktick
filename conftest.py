"""Root pytest configuration.

The dev/test web container loads the real ``.env`` — ``HCAPTCHA_SECRET`` and
``HCAPTCHA_SITEKEY`` are set there — while CI runs without them. Signup is
captcha-gated while ``HCAPTCHA_SECRET`` is configured (issue #382), so an
ambient secret would otherwise make every signup POST fail closed in local
Docker runs but pass in CI.

Reset both hCaptcha settings for every test so the suite is deterministic.
Tests that exercise the captcha opt back in explicitly via the ``settings``
fixture (see tests/test_signup_captcha.py and
checktick_app/surveys/tests/test_thankyou_and_captcha.py), which overrides
this default.
"""

import pytest


@pytest.fixture(autouse=True)
def _hcaptcha_disabled_by_default(settings):
    """Run every test with hCaptcha unconfigured unless the test opts in."""
    settings.HCAPTCHA_SECRET = ""
    settings.HCAPTCHA_SITEKEY = ""


@pytest.fixture(autouse=True)
def _ratelimit_disabled_by_default(settings):
    """Disable view-level rate limits for every test.

    The ``PYTEST_CURRENT_TEST`` guard in settings.py runs before pytest sets
    that variable, so ``@ratelimit`` decorators stay active and request-heavy
    modules (e.g. take-page tests) trip the per-IP limits of later modules —
    all test clients share 127.0.0.1.
    """
    settings.RATELIMIT_ENABLE = False
