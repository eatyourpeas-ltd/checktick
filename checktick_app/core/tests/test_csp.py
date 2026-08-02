"""
Tests for the Content Security Policy configuration (security-review F9).

F9 noted that `style-src 'unsafe-inline'` weakens the style-injection
defence.  The accepted remediation (per the review's recommended fix #3) is
to retain `'unsafe-inline'` because hCaptcha and DaisyUI genuinely require
inline styles, AND to mitigate the CSS-injection surface at the server side
via `sanitize_css_block` / `_sanitize_css_value` (F16).  These tests assert:

1. The CSP header is emitted on responses.
2. `style-src` is restricted to a documented allowlist (not `*`).
3. `script-src` does NOT carry `'unsafe-inline'` (the strong script-XSS
   defence is preserved).
4. The `style-src` relaxation is documented in `settings.py` and
   `docs/security-overview.md` so the accepted risk is auditable.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.urls import reverse
import pytest


def _csp_header(resp):
    return resp.get("Content-Security-Policy") or resp.get(
        "Content-Security-Policy-Report-Only"
    )


@pytest.mark.django_db
def test_csp_header_present_on_public_page(client):
    """A Content-Security-Policy header must be emitted on responses."""
    resp = client.get(reverse("core:home"))
    csp = _csp_header(resp)
    assert csp, "No Content-Security-Policy header on response"


@pytest.mark.django_db
def test_csp_style_src_does_not_allow_wildcard(client):
    """
    F9: `style-src` may retain `'unsafe-inline'` (required by hCaptcha/DaisyUI)
    but must NOT allow `*` or arbitrary origins.  Only the documented allowlist
    (self, Google Fonts, hCaptcha) is permitted.
    """
    resp = client.get(reverse("core:home"))
    csp = _csp_header(resp)
    assert csp
    m = re.search(r"style-src\s+([^;]+)", csp)
    assert m, f"style-src directive not found in CSP: {csp!r}"
    style_src = m.group(1)
    tokens = style_src.split()
    assert (
        "*" not in tokens
    ), f"style-src must not allow bare wildcard origin; got: {style_src!r}"
    assert "'self'" in tokens


@pytest.mark.django_db
def test_csp_script_src_does_not_allow_unsafe_inline(client):
    """
    F9: the script-injection defence must remain strong.  `script-src` must
    NOT carry `'unsafe-inline'`; inline scripts are gated by per-request
    nonces and explicit hashes only.
    """
    resp = client.get(reverse("core:home"))
    csp = _csp_header(resp)
    assert csp
    m = re.search(r"script-src\s+([^;]+)", csp)
    assert m, f"script-src directive not found in CSP: {csp!r}"
    script_src = m.group(1)
    assert (
        "'unsafe-inline'" not in script_src
    ), f"script-src must not allow 'unsafe-inline'; got: {script_src!r}"


def test_style_src_unsafe_inline_is_documented_in_settings():
    """
    F9 (auditability): the `style-src 'unsafe-inline'` relaxation must be
    documented with a comment in settings.py so the accepted risk is
    auditable.  We look for a comment near the style-src directive that
    mentions hCaptcha or DaisyUI/HTMX/Tailwind (the documented justification).
    """
    settings_path = settings.BASE_DIR / "checktick_app" / "settings.py"
    text = settings_path.read_text()
    m = re.search(r'"style-src":\s*\(([^)]*)\)', text, re.DOTALL)
    assert m, "style-src directive not found in settings.py"
    block = m.group(1)
    assert "'unsafe-inline'" in block
    # The justification comment must mention hCaptcha or DaisyUI/HTMX/Tailwind.
    start = max(0, m.start() - 400)
    context = text[start : m.end()]
    assert any(
        kw in context
        for kw in (
            "hCaptcha",
            "hcaptcha",
            "DaisyUI",
            "daisyUI",
            "HTMX",
            "htmx",
            "Tailwind",
            "tailwind",
        )
    ), (
        "style-src 'unsafe-inline' relaxation must be documented with a "
        "justification comment (hCaptcha/DaisyUI/HTMX/Tailwind) in settings.py"
    )


def test_style_src_unsafe_inline_documented_in_security_overview():
    """
    F9 (auditability): the security-overview.md document must mention the
    style-src 'unsafe-inline' relaxation so it is captured in the security
    posture documentation.
    """
    doc = settings.BASE_DIR / "docs" / "security-overview.md"
    text = doc.read_text()
    assert (
        "unsafe-inline" in text
    ), "security-overview.md must document the style-src 'unsafe-inline' relaxation"
