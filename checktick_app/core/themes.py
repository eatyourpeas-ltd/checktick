"""
Utilities for managing daisyUI themes.

This module provides functions to:
- Get CSS variables from daisyUI preset themes
- Parse custom theme configuration objects
- Convert theme data to injectable CSS
"""
from __future__ import annotations

import re
from typing import Dict, Optional

# DaisyUI theme presets categorized by color scheme
LIGHT_THEMES = [
    "light",
    "cupcake",
    "bumblebee",
    "emerald",
    "corporate",
    "retro",
    "cyberpunk",
    "valentine",
    "garden",
    "lofi",
    "pastel",
    "fantasy",
    "wireframe",
    "cmyk",
    "autumn",
    "acid",
    "lemonade",
    "winter",
    "nord",
    "sunset",
]

DARK_THEMES = [
    "dark",
    "synthwave",
    "halloween",
    "forest",
    "aqua",
    "black",
    "luxury",
    "dracula",
    "business",
    "night",
    "coffee",
    "dim",
]

ALL_THEMES = LIGHT_THEMES + DARK_THEMES


def get_theme_color_scheme(theme_name: str) -> str:
    """
    Get the color-scheme (light/dark) for a daisyUI theme.

    Args:
        theme_name: Name of the daisyUI theme preset

    Returns:
        "light" or "dark"
    """
    if theme_name in LIGHT_THEMES:
        return "light"
    elif theme_name in DARK_THEMES:
        return "dark"
    return "light"  # Default to light


def parse_custom_theme_config(config_text: str) -> Optional[Dict[str, str]]:
    """
    Parse a custom daisyUI theme configuration object from text.

    Supports the format from daisyUI theme builder:
    ```
    @plugin "daisyui/theme" {
      name: "mytheme";
      --color-primary: #6d5aa5;
      --radius-box: 0.25rem;
      ...
    }
    ```

    Args:
        config_text: Raw text containing the theme configuration

    Returns:
        Dictionary of CSS variable names to values, or None if parsing fails
    """
    if not config_text or not config_text.strip():
        return None

    theme_vars = {}

    # Match CSS variable declarations: --var-name: value;
    var_pattern = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")

    for match in var_pattern.finditer(config_text):
        var_name = match.group(1).strip()
        var_value = match.group(2).strip()
        theme_vars[var_name] = var_value

    # Also extract name and color-scheme if present
    name_match = re.search(r'name\s*:\s*"([^"]+)"', config_text)
    if name_match:
        theme_vars["_name"] = name_match.group(1)

    scheme_match = re.search(r'color-scheme\s*:\s*"([^"]+)"', config_text)
    if scheme_match:
        theme_vars["_color_scheme"] = scheme_match.group(1)
    elif "color-scheme" in config_text:
        # Try without quotes
        scheme_match = re.search(r"color-scheme\s*:\s*(\w+)", config_text)
        if scheme_match:
            theme_vars["_color_scheme"] = scheme_match.group(1)

    return theme_vars if theme_vars else None


def theme_vars_to_css(theme_vars: Dict[str, str], color_scheme: Optional[str] = None) -> str:
    """
    Convert theme variables dictionary to CSS variable declarations.

    Args:
        theme_vars: Dictionary of CSS variable names to values
        color_scheme: Optional color-scheme override ("light" or "dark")

    Returns:
        CSS string with variable declarations
    """
    css_lines = []

    # Add color-scheme if provided or extracted
    scheme = color_scheme or theme_vars.get("_color_scheme", "light")
    css_lines.append(f"color-scheme: {scheme};")

    # Add all CSS variables (skip metadata keys starting with _)
    for var_name, var_value in sorted(theme_vars.items()):
        if not var_name.startswith("_"):
            css_lines.append(f"{var_name}: {var_value};")

    return "\n    ".join(css_lines)


def get_preset_theme_reference(preset_name: str) -> str:
    """
    Generate CSS to reference a daisyUI preset theme.

    Instead of copying all variables, we can use CSS custom property inheritance
    by applying the preset theme as a base and overriding as needed.

    Args:
        preset_name: Name of the daisyUI preset theme

    Returns:
        CSS comment referencing the preset theme
    """
    color_scheme = get_theme_color_scheme(preset_name)
    return f"""color-scheme: {color_scheme};
    /* Base theme: {preset_name} */
    /* Variables inherited from [data-theme="{preset_name}"] */"""


def generate_theme_css_for_brand(
    preset_light: Optional[str] = None,
    preset_dark: Optional[str] = None,
    custom_css_light: Optional[str] = None,
    custom_css_dark: Optional[str] = None,
) -> tuple[str, str]:
    """
    Generate CSS for checktick-light and checktick-dark themes based on brand settings.

    Args:
        preset_light: daisyUI preset name for light theme (default: "wireframe")
        preset_dark: daisyUI preset name for dark theme (default: "business")
        custom_css_light: Custom CSS overrides for light theme
        custom_css_dark: Custom CSS overrides for dark theme

    Returns:
        Tuple of (light_css, dark_css) ready to inject in <style> tags
    """
    preset_light = preset_light or "wireframe"
    preset_dark = preset_dark or "business"

    # For light theme
    if custom_css_light and custom_css_light.strip():
        # Try to parse as custom theme config
        parsed = parse_custom_theme_config(custom_css_light)
        if parsed:
            light_css = theme_vars_to_css(parsed)
        else:
            # Use as raw CSS
            light_css = custom_css_light
    else:
        # Use preset reference
        light_css = get_preset_theme_reference(preset_light)

    # For dark theme
    if custom_css_dark and custom_css_dark.strip():
        parsed = parse_custom_theme_config(custom_css_dark)
        if parsed:
            dark_css = theme_vars_to_css(parsed)
        else:
            dark_css = custom_css_dark
    else:
        dark_css = get_preset_theme_reference(preset_dark)

    return light_css, dark_css
