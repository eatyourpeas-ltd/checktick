"""Shared hCaptcha verification.

Extracted from ``checktick_app/surveys/views.py`` (issue #382) so both the
survey-response flow and the signup flow enforce the same check.

Convention: verification is only enforced when ``settings.HCAPTCHA_SECRET``
is configured. An unset secret means self-hosters (and tests) run without
a captcha — callers fail closed only when the secret is set.
"""

import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://hcaptcha.com/siteverify"


def verify_captcha(request: HttpRequest) -> bool:
    """Server-side hCaptcha verification.

    Expects the POST token in 'h-captcha-response' and verifies it against
    https://hcaptcha.com/siteverify using settings.HCAPTCHA_SECRET.

    Returns True when verification passes or when no secret is configured
    (captcha disabled). Returns False when a secret is set but the token is
    missing, rejected, or the siteverify call fails — callers enforce the
    result (survey.captcha_required for responses; signup fails closed).
    """
    secret = getattr(settings, "HCAPTCHA_SECRET", None)
    if not secret:
        # Not configured; treat as pass. Enforcement happens in views based
        # on survey.captcha_required / the signup fail-closed gate.
        return True
    token = request.POST.get("h-captcha-response")
    if not token:
        return False
    try:
        data = urllib.parse.urlencode(
            {
                "secret": secret,
                "response": token,
                "remoteip": request.META.get("REMOTE_ADDR", ""),
            }
        ).encode()
        req = urllib.request.Request(SITEVERIFY_URL, data=data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("success"))
    except Exception:
        # Network/parse failures fail closed: when a secret is configured,
        # a signup or response must not be accepted on an unverifiable token.
        return False
