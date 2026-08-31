"""Theme resolution and colour conversion for branded emails.

Email clients (Gmail, Outlook, Apple Mail webmail variants) do not support
``oklch()`` or modern CSS colour functions, so every colour that reaches
``emails/base_email.html`` must be a plain sRGB value (hex or rgb()).

This module provides:

- :func:`oklch_to_hex` — pure-Python OKLCH → sRGB conversion (no deps).
- ``PRESET_COLORS`` — daisyUI v5 preset theme variables, generated from
  ``node_modules/daisyui/theme/*.css`` (see ``email_preset_colors.py``).
- :func:`resolve_email_colors` — pick the best colour set for a platform /
  organisation / survey theme configuration, in the same precedence order
  as the web cascade (survey → organisation → platform).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional

from checktick_app.core.email_preset_colors import PRESET_COLORS

# Variables the email template consumes, mapped from daisyUI names.
_EMAIL_VARS = (
    "primary",
    "primary-content",
    "accent",
    "accent-content",
    "base-100",
    "base-200",
    "base-300",
    "base-content",
)


def _oklab_to_linear_srgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    """Convert OKLab to linear-light sRGB (Björn Ottosson's reference math)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l_c = l_ * l_ * l_
    m_c = m_ * m_ * m_
    s_c = s_ * s_ * s_

    r = +4.0767416621 * l_c - 3.3077115913 * m_c + 0.2309699292 * s_c
    g = -1.2684380046 * l_c + 2.6097574011 * m_c - 0.3413193965 * s_c
    b2 = -0.0041960863 * l_c - 0.7034186147 * m_c + 1.7076147010 * s_c
    return r, g, b2


def _linear_to_srgb_channel(c: float) -> int:
    """Gamma-encode one linear channel and clamp to 0-255."""
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0, min(255, round(v * 255)))


def oklch_to_hex(L: float, C: float, H: float) -> str:
    """Convert OKLCH (L in 0-1 or 0-100, C in 0-1, H in degrees) to #rrggbb."""
    if L > 1:  # tolerate percentage lightness ("15.906%")
        L = L / 100
    h_rad = math.radians(H)
    r, g, b = _oklab_to_linear_srgb(L, C * math.cos(h_rad), C * math.sin(h_rad))
    return "#{:02x}{:02x}{:02x}".format(
        _linear_to_srgb_channel(r),
        _linear_to_srgb_channel(g),
        _linear_to_srgb_channel(b),
    )


def to_email_safe_color(value: str) -> str:
    """Convert any CSS colour string to an email-safe sRGB value.

    Handles oklch() function form, raw oklch triplets ("0.65 0.22 256"),
    and passes through hex / rgb() / hsl() / named colours unchanged.
    Returns "" for empty or unparseable input.
    """
    if not value:
        return ""
    value = value.strip()

    m = re.match(
        r"^oklch\(\s*([\d.]+)%?\s+([\d.]+)%?\s+([\d.]+)\s*(?:/[^)]*)?\)$", value
    )
    if m:
        try:
            return oklch_to_hex(float(m.group(1)), float(m.group(2)), float(m.group(3)))
        except (ValueError, OverflowError):
            return ""

    # Raw triplet form emitted by some daisyUI builder output: "0.65 0.22 256"
    m = re.match(r"^(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)$", value)
    if m:
        try:
            return oklch_to_hex(float(m.group(1)), float(m.group(2)), float(m.group(3)))
        except (ValueError, OverflowError):
            return ""

    if re.match(r"^#[0-9a-fA-F]{3,8}$", value):
        return value
    if re.match(r"^(rgb|rgba|hsl|hsla)\s*\([^)]*\)$", value):
        return value
    if re.fullmatch(r"[a-z]+", value):
        return value  # named colour
    return ""


def preset_colors_for(preset_name: str) -> Dict[str, str]:
    """Return email-safe colours for a daisyUI preset, or {} if unknown."""
    preset = PRESET_COLORS.get(preset_name or "")
    if not preset:
        return {}
    colors: Dict[str, str] = {}
    for key, value in preset.items():
        if key.startswith("_"):
            continue
        safe = to_email_safe_color(value)
        if safe:
            colors[key] = safe
    return colors


def colors_from_theme_css(theme_css: str) -> Dict[str, str]:
    """Extract email-safe colours from custom theme CSS (daisyUI variables)."""
    if not theme_css:
        return {}
    colors: Dict[str, str] = {}
    for m in re.finditer(r"--color-?([a-z][a-z0-9-]*)\s*:\s*([^;]+);", theme_css):
        name = m.group(1)
        if name.startswith("color-"):
            name = name[len("color-") :]
        safe = to_email_safe_color(m.group(2).strip())
        if safe:
            colors[name] = safe
    return colors


def resolve_email_colors(
    preset_name: str = "",
    theme_css: str = "",
    fallback: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Resolve email colours for one cascade level.

    Custom theme CSS wins over the preset name; if neither yields colours,
    ``fallback`` (the next level up, or platform defaults) is returned.

    Returns a dict with the keys the email template needs:
    ``primary_color``, ``primary_content_color``, ``accent_color``,
    ``background_color``, ``text_color``, ``footer_bg_color``,
    ``border_color``.
    """
    colors = colors_from_theme_css(theme_css)
    if not colors:
        colors = preset_colors_for(preset_name)
    if not colors:
        colors = dict(fallback or {})

    # Fallback dicts may arrive with either daisyUI names ("primary") from
    # an upstream cascade level or template keys ("primary_color") from the
    # caller; normalise to daisyUI names for lookup below.
    for daisy_name, template_key in (
        ("primary", "primary_color"),
        ("primary-content", "primary_content_color"),
        ("accent", "accent_color"),
        ("base-100", "background_color"),
        ("base-content", "text_color"),
        ("base-200", "footer_bg_color"),
        ("base-300", "border_color"),
    ):
        if not colors.get(daisy_name) and colors.get(template_key):
            colors[daisy_name] = colors[template_key]

    def get(name: str, default: str) -> str:
        return colors.get(name) or default

    return {
        "primary_color": get("primary", "#3b82f6"),
        "primary_content_color": get("primary-content", "#ffffff"),
        "accent_color": get("accent", "#f59e0b"),
        "background_color": get("base-100", "#ffffff"),
        "text_color": get("base-content", "#1a1a1a"),
        "footer_bg_color": get("base-200", "#f8f9fa"),
        "border_color": get("base-300", "#e9ecef"),
    }


def resolve_cascade_colors(
    survey_style: Optional[Dict[str, Any]] = None,
    organization: Any = None,
    platform_preset: str = "",
    platform_theme_css: str = "",
) -> Dict[str, str]:
    """Resolve colours through the full 3-tier theme cascade.

    Precedence (highest first): survey style → organisation theme →
    platform theme → built-in defaults. Mirrors the web cascade in
    ``context_processors.branding``.
    """
    platform_colors = resolve_email_colors(platform_preset, platform_theme_css)

    org_colors = platform_colors
    if organization is not None:
        org_preset = getattr(organization, "theme_preset_light", "") or platform_preset
        org_css = getattr(organization, "theme_light_css", "") or platform_theme_css
        org_colors = resolve_email_colors(org_preset, org_css, platform_colors)

    style = survey_style or {}
    survey_preset = style.get("theme_light") or style.get("theme_name") or ""
    survey_css = style.get("custom_css") or style.get("theme_light_css") or ""
    return resolve_email_colors(survey_preset, survey_css, org_colors)
