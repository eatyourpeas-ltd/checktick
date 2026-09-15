"""Server-side Markdown → HTML rendering with strict sanitisation.

This module is the single entry point for rendering author-supplied
Markdown content (currently content-block bodies) into HTML that is safe
to emit inside Django templates via ``|safe``.

Pipeline:

1. ``markdown.markdown`` converts Markdown to HTML using a conservative
   extension set (``extra``, ``nl2br``, ``sane_lists``).  Python-Markdown
   passes raw HTML through by default, so step 2 is mandatory.
2. ``nh3.clean`` sanitises the resulting HTML with an explicit allowlist
   of tags and attributes.  Anything not in the allowlist is stripped.
   ``javascript:``, ``data:`` and other dangerous URI schemes are removed
   from ``href``/``src`` attributes by nh3's built-in URL scheme filter.

The allowlist is deliberately narrow: only the structural and inline
tags needed for authored survey content (headings, paragraphs, lists,
links, emphasis, code, blockquotes, images).  No ``<script>``, ``<style>``,
``<iframe>``, ``<form>``, ``<input>``, or event-handler attributes survive.

See ``docs/security-overview.md`` §A03 (XSS Prevention) for the attack
surface reference.
"""

from __future__ import annotations

from django.utils.safestring import SafeString, mark_safe
import markdown
import nh3

# --- Markdown extension set --------------------------------------------------
# ``extra`` enables tables, fenced code, footnotes, and abbreviations.
# ``nl2br`` converts single newlines to <br> (author-friendly).
# ``sane_lists`` restricts list behaviour to sane defaults.
_MARKDOWN_EXTENSIONS: list[str] = ["extra", "nl2br", "sane_lists"]

# --- nh3 allowlist ----------------------------------------------------------
# Only the tags and attributes needed for authored content blocks.
# No script, style, iframe, form, input, object, embed, or media tags.
_ALLOWED_TAGS: set[str] = {
    # Block structure
    "p",
    "br",
    "hr",
    "blockquote",
    "pre",
    # Headings
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    # Lists
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    # Tables (from ``extra``)
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    # Inline
    "a",
    "strong",
    "em",
    "code",
    "span",
    "sub",
    "sup",
    "abbr",
    "cite",
    "q",
    # Images (content blocks may embed non-medical imagery)
    "img",
    # Fenced code blocks
    "div",
}

# Attributes allowed on specific tags.  ``*`` applies to all allowed tags.
_ALLOWED_ATTRIBUTES: dict[str, set[str] | None] = {
    "*": {"class", "id"},
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "div": {"class"},
}

# URL schemes permitted on ``href``/``src``.  nh3 enforces this by default;
# listed here for documentation and test stability.
_ALLOWED_URL_SCHEMES: set[str] = {"http", "https", "mailto"}


def render_content_block_markdown(body_md: str) -> SafeString:
    """Render a content-block Markdown body to sanitised, safe HTML.

    Args:
        body_md: Raw Markdown text authored by a survey author (e.g. the
            ``options["body_md"]`` value of a ``content_block`` question).

    Returns:
        A ``SafeString`` suitable for direct emission in a Django template
        (``{{ body_html }}`` without ``|safe`` is fine — the value is
        already marked safe and sanitised).

    Empty input returns an empty ``SafeString``.
    """
    if not body_md or not body_md.strip():
        return mark_safe("")  # nosemgrep

    raw_html = markdown.markdown(body_md, extensions=_MARKDOWN_EXTENSIONS)

    cleaned: str = nh3.clean(
        raw_html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
        # Strip any HTML comments (e.g. conditional-comment IE vectors).
        strip_comments=True,
        # Keep link rel attributes we set ourselves; nh3 adds rel="noopener"
        # to target="_blank" links automatically when link_rel is set.
        link_rel="noopener noreferrer",
    )

    return mark_safe(cleaned)  # nosemgrep


def sanitise_link_url(url: str) -> str:
    """Validate a content-block link URL against the scheme allowlist.

    Returns the URL if it uses an allowed scheme (``http``, ``https``,
    ``mailto``), or an empty string if the scheme is dangerous or missing.
    Used at save time (builder form, parser) so bad URLs never reach the
    rendered page.
    """
    if not url:
        return ""
    cleaned = url.strip()
    # Block protocol-relative URLs (//evil.com) — they inherit the
    # page scheme and could resolve to an attacker host.
    if cleaned.startswith("//"):
        return ""
    # Allow relative URLs (no scheme) — they resolve to the current host.
    if cleaned.startswith("/"):
        return cleaned
    scheme_sep = cleaned.find(":")
    if scheme_sep == -1:
        # No scheme — treat as relative and allow.
        return cleaned
    scheme = cleaned[:scheme_sep].lower()
    if scheme in _ALLOWED_URL_SCHEMES:
        return cleaned
    return ""


__all__: list[str] = [
    "render_content_block_markdown",
    "sanitise_link_url",
]
