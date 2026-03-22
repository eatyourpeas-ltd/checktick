import re
from typing import Dict

from django.utils.safestring import SafeString, mark_safe

_VAR_LINE_RE = re.compile(r"--(?P<key>[a-zA-Z0-9_-]+)\s*:\s*(?P<val>[^;]+);?")


def _sanitize_css_value(val: str) -> str:
    """Strip characters that could break out of a CSS value context.

    Removes:
    - Angle brackets  (prevents </style> breakout and <script> injection)
    - Curly braces    (prevents CSS block injection)
    - Semicolons      (prevents CSS property injection chain)
    - url() references (prevents CSS-based data exfiltration)
    - Bare https?://  URLs left behind once a url() opener is stripped

    Valid CSS values for colours, sizes, and font names never need these.
    """
    val = (
        val.replace("<", "")
        .replace(">", "")
        .replace("{", "")
        .replace("}", "")
        .replace(";", "")
    )
    # Strip url() references (with or without a closing paren)
    val = re.sub(r"url\s*\([^)]*\)?", "", val, flags=re.IGNORECASE)
    # Strip any bare URL remaining after the url() opener was stripped
    val = re.sub(r"https?://\S*", "", val, flags=re.IGNORECASE)
    return val


def sanitize_font_family(val: str) -> SafeString:
    """Sanitize a CSS font-family property value and return a SafeString.

    Font-family values are rendered inside <style> blocks. Stripping the
    dangerous characters here means the value is safe to output without |safe,
    and returning SafeString prevents Django from re-escaping the CSS single
    quotes that surround multi-word font names (e.g. 'DIN Round Pro').
    """
    # Unwrap an existing SafeString so we operate on plain text
    raw = str(val)
    raw = raw.replace("{", "").replace("}", "").replace(";", "")
    raw = re.sub(r"url\s*\([^)]*\)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"https?://\S*", "", raw, flags=re.IGNORECASE)
    # HTML-encode angle brackets and ampersands to prevent </style> breakout and
    # entity injection.  Single-quotes are intentionally NOT encoded: they are
    # valid CSS font-family syntax (e.g. 'DIN Round Pro') and browsers do not
    # interpret HTML entities inside <style> blocks, so encoding them would break
    # font rendering.  Angle brackets are the only characters that can close the
    # <style> block and inject markup.
    raw = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return mark_safe(  # nosemgrep: python.django.security.audit.avoid-mark-safe.avoid-mark-safe
        raw
    )


def sanitize_css_block(css: str) -> str:
    """Strip characters that could break out of a <style> block.

    Used as a last-resort guard on any CSS string rendered with |safe.
    Removes angle brackets that would allow </style> breakout.
    """
    return css.replace("<", "").replace(">", "")


def _map_key(k: str) -> str:
    # Accept already-correct DaisyUI vars as-is
    if k in {
        "p",
        "pc",
        "s",
        "sc",
        "a",
        "ac",
        "n",
        "nc",
        "b1",
        "b2",
        "b3",
        "bc",
        "in",
        "inc",
        "su",
        "suc",
        "wa",
        "wac",
        "er",
        "erc",
    }:
        return f"--{k}"
    # Map builder --color-* and base/neutral names to DaisyUI runtime vars
    m: Dict[str, str] = {
        "color-primary": "--p",
        "color-primary-content": "--pc",
        "color-secondary": "--s",
        "color-secondary-content": "--sc",
        "color-accent": "--a",
        "color-accent-content": "--ac",
        "color-neutral": "--n",
        "color-neutral-content": "--nc",
        "color-base-100": "--b1",
        "color-base-200": "--b2",
        "color-base-300": "--b3",
        "color-base-content": "--bc",
        "color-info": "--in",
        "color-info-content": "--inc",
        "color-success": "--su",
        "color-success-content": "--suc",
        "color-warning": "--wa",
        "color-warning-content": "--wac",
        "color-error": "--er",
        "color-error-content": "--erc",
    }
    if k in m:
        return m[k]
    # Pass through radius/depth/size vars in builder format
    if k.startswith("radius-") or k in {
        "border",
        "depth",
        "noise",
        "size-selector",
        "size-field",
    }:
        return f"--{k}"
    # Unknown var: ignore by returning empty key
    return ""


def normalize_daisyui_builder_css(raw: str) -> str:
    """Extract CSS variable declarations from a DaisyUI builder snippet and
    map them to DaisyUI runtime variables.

    Accepts either lines with --color-* or already-correct --p/--b1 vars.
    Returns a CSS string with semicolon-terminated declarations, suitable
    to inject inside a [data-theme] rule.
    """
    if not raw:
        return ""
    out: Dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        # Skip wrapper lines like @plugin/name, name:, default:, braces
        if (
            not line
            or line.startswith("@")
            or line.endswith("{")
            or line == "}"
            or ":" in line
            and not line.strip().startswith("--")
        ):
            # allow-only var lines (starting with --)
            pass
        m = _VAR_LINE_RE.search(line)
        if not m:
            continue
        key = m.group("key")
        val = m.group("val").strip().rstrip(";")
        mapped = _map_key(key)
        if mapped:
            out[mapped] = _sanitize_css_value(val)
    # Build CSS lines
    return "\n".join(f"  {k}: {v};" for k, v in out.items())
