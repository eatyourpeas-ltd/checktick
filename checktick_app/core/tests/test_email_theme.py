"""Unit tests for `checktick_app/core/email_theme.py`.

Covers:

- OKLCH → sRGB hex conversion (against known daisyUI / Tailwind values).
- Email-safe colour normalisation (oklch function form, raw triplets,
  passthrough of hex/rgb/hsl, rejection of garbage).
- Preset colour resolution for daisyUI themes.
- Cascade resolution: survey → organisation → platform → defaults.
"""

from __future__ import annotations

from types import SimpleNamespace

from checktick_app.core.email_theme import (
    oklch_to_hex,
    preset_colors_for,
    resolve_cascade_colors,
    resolve_email_colors,
    to_email_safe_color,
)

# ---------------------------------------------------------------------------
# oklch_to_hex
# ---------------------------------------------------------------------------


def test_oklch_white_and_black():
    assert oklch_to_hex(1.0, 0, 0) == "#ffffff"
    assert oklch_to_hex(0.0, 0, 0) == "#000000"


def test_oklch_percentage_lightness():
    # daisyUI lofi primary: oklch(15.906% 0 0) — near-black
    assert oklch_to_hex(15.906, 0, 0) == oklch_to_hex(0.15906, 0, 0)


def test_oklch_known_color():
    # CSS Color 4 reference round-trips: sRGB primaries expressed in oklch
    # must convert back to their original hex values.
    assert oklch_to_hex(0.452, 0.313, 264.052) == "#0000ff"  # blue
    assert oklch_to_hex(0.628, 0.258, 29.234) == "#ff0000"  # red
    assert oklch_to_hex(0.866, 0.295, 142.495) == "#00ff00"  # green


def test_oklch_neutral_gray():
    # lofi primary oklch(15.906% 0 0) should be a neutral dark gray
    hex_val = oklch_to_hex(0.15906, 0, 0)
    r, g, b = int(hex_val[1:3], 16), int(hex_val[3:5], 16), int(hex_val[5:7], 16)
    assert r == g == b
    assert 0 <= r <= 40


# ---------------------------------------------------------------------------
# to_email_safe_color
# ---------------------------------------------------------------------------


def test_passthrough_hex():
    assert to_email_safe_color("#ff0000") == "#ff0000"


def test_passthrough_rgb_hsl():
    assert to_email_safe_color("rgb(1, 2, 3)") == "rgb(1, 2, 3)"
    assert to_email_safe_color("hsl(210, 50%, 40%)") == "hsl(210, 50%, 40%)"


def test_oklch_function_converted_to_hex():
    out = to_email_safe_color("oklch(62.3% 0.214 259.815)")
    assert out.startswith("#")
    assert len(out) == 7


def test_oklch_raw_triplet_converted_to_hex():
    out = to_email_safe_color("0.623 0.214 259.815")
    assert out.startswith("#")
    assert len(out) == 7


def test_empty_and_garbage_return_empty():
    assert to_email_safe_color("") == ""
    assert to_email_safe_color("   ") == ""
    assert to_email_safe_color("not a color") == ""


# ---------------------------------------------------------------------------
# preset_colors_for
# ---------------------------------------------------------------------------


def test_known_preset_returns_email_safe_colors():
    colors = preset_colors_for("corporate")
    assert colors["primary"].startswith("#")
    assert colors["primary-content"].startswith("#")
    assert "oklch" not in colors["primary"]


def test_unknown_preset_returns_empty():
    assert preset_colors_for("nonexistent-theme") == {}
    assert preset_colors_for("") == {}


def test_lofi_preset_is_monochrome():
    colors = preset_colors_for("lofi")
    assert colors["primary"] == colors["primary"].lower()
    # lofi primary is near-black
    r = int(colors["primary"][1:3], 16)
    assert r <= 40


# ---------------------------------------------------------------------------
# resolve_email_colors
# ---------------------------------------------------------------------------


def test_resolve_prefers_custom_css_over_preset():
    css = "--color-primary: #123456;"
    colors = resolve_email_colors("corporate", css)
    assert colors["primary_color"] == "#123456"


def test_resolve_falls_back_to_preset():
    colors = resolve_email_colors("corporate", "")
    assert colors["primary_color"].startswith("#")
    assert colors["primary_color"] != "#3b82f6"  # not the hardcoded default


def test_resolve_falls_back_to_defaults_when_unknown():
    colors = resolve_email_colors("nonexistent", "")
    assert colors["primary_color"] == "#3b82f6"
    assert colors["primary_content_color"] == "#ffffff"
    assert colors["footer_bg_color"] == "#f8f9fa"


def test_resolve_returns_all_template_keys():
    colors = resolve_email_colors("corporate", "")
    for key in (
        "primary_color",
        "primary_content_color",
        "accent_color",
        "background_color",
        "text_color",
        "footer_bg_color",
        "border_color",
    ):
        assert key in colors


# ---------------------------------------------------------------------------
# resolve_cascade_colors
# ---------------------------------------------------------------------------


def test_cascade_survey_overrides_org_and_platform():
    org = SimpleNamespace(theme_preset_light="corporate", theme_light_css="")
    colors = resolve_cascade_colors(
        survey_style={"theme_light": "forest"},
        organization=org,
        platform_preset="lofi",
    )
    # forest primary is a green; corporate primary is blue; lofi is near-black
    assert colors["primary_color"] == preset_colors_for("forest")["primary"]


def test_cascade_org_overrides_platform():
    org = SimpleNamespace(theme_preset_light="corporate", theme_light_css="")
    colors = resolve_cascade_colors(
        survey_style={}, organization=org, platform_preset="lofi"
    )
    assert colors["primary_color"] == preset_colors_for("corporate")["primary"]


def test_cascade_platform_used_when_no_overrides():
    colors = resolve_cascade_colors(
        survey_style={}, organization=None, platform_preset="corporate"
    )
    assert colors["primary_color"] == preset_colors_for("corporate")["primary"]


def test_cascade_custom_survey_css_wins():
    org = SimpleNamespace(theme_preset_light="corporate", theme_light_css="")
    colors = resolve_cascade_colors(
        survey_style={"custom_css": "--color-primary: #abcdef;"},
        organization=org,
        platform_preset="lofi",
    )
    assert colors["primary_color"] == "#abcdef"


def test_cascade_defaults_when_nothing_set():
    colors = resolve_cascade_colors(
        survey_style={}, organization=None, platform_preset=""
    )
    assert colors["primary_color"] == "#3b82f6"


# ---------------------------------------------------------------------------
# Rendered email HTML — escaping and injection regression guards
# (mirrors tests/test_style_injection_security.py Surfaces 8/9, but for the
# email template surface, which renders brand values inside <style>.)
# ---------------------------------------------------------------------------


def _render_email(brand):
    from django.template.loader import render_to_string

    return render_to_string(
        "emails/base_email.html",
        {
            "subject": "Test",
            "content": "<p>Hello</p>",
            "brand": brand,
            "site_url": "https://example.com",
        },
    )


def test_rendered_email_has_no_html_escaped_font_quotes():
    """Browsers do not decode HTML entities inside <style>, so escaped
    quotes (&#x27;) invalidate every font-family declaration. Font stacks
    must render raw (they are pre-sanitised via sanitize_font_family)."""
    from checktick_app.core.email_utils import get_platform_branding

    html = _render_email(get_platform_branding())
    assert "&#x27;" not in html, "font quotes must not be HTML-escaped in <style>"
    assert "font-family: '" in html


def test_rendered_email_font_face_css_not_escaped():
    """The DIN Round Pro @font-face block must render with raw quotes so the
    rules are valid CSS (regression: pre-fix it rendered as &#x27;)."""
    from django.test import override_settings

    from checktick_app.core.email_utils import get_platform_branding

    with override_settings(SITE_URL="https://example.com"):
        brand = get_platform_branding()
    if not brand["font_face_css"]:
        return  # DIN Round Pro not configured in this environment
    html = _render_email(brand)
    assert "@font-face" in html
    assert "font-family: 'DIN Round Pro'" in html
    assert "&#x27;" not in html


def test_rendered_email_blocks_font_style_injection():
    """Surface 8 for emails: a CSS-injection payload in survey.style fonts
    must be stripped before it reaches the rendered <style> block."""
    from checktick_app.core.email_utils import get_survey_branding

    class FakeSurvey:
        name = "Evil"
        slug = "evil"
        organization = None
        style = {
            "font_heading": "Arial; } h1 { background: url(https://evil.example.com/?",
            "font_body": "'Roboto', sans-serif; } a { color: red; }",
        }

    brand = get_survey_branding(FakeSurvey())
    html = _render_email(brand)
    assert "evil.example.com" not in html, "CSS injection must not reach email HTML"
    assert "color: red; }" not in html, "CSS rule injection must not reach email HTML"


def test_rendered_email_colors_are_email_safe():
    """No oklch()/oklab() values may reach the rendered email HTML — most
    email clients do not support modern CSS colour functions."""
    import re

    from checktick_app.core.email_utils import get_platform_branding

    html = _render_email(get_platform_branding())
    assert not re.search(r"oklch\(|oklab\(", html), "raw oklch leaked into email"
