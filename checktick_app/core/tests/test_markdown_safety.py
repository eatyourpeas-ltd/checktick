"""Tests for the content-block Markdown sanitisation pipeline.

See ``checktick_app/core/markdown_safety.py`` and
``docs/security-overview.md`` §A03 (XSS Prevention — Content Block Markdown).
"""

from __future__ import annotations

import pytest

from checktick_app.core.markdown_safety import (
    render_content_block_markdown,
    sanitise_link_url,
)

# --- Basic rendering --------------------------------------------------------


def test_empty_input_returns_empty():
    assert render_content_block_markdown("") == ""
    assert render_content_block_markdown("   ") == ""


def test_plain_markdown_renders():
    html = render_content_block_markdown("**bold** and *italic*")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_headings_render():
    html = render_content_block_markdown("# Title\n\n## Subtitle")
    assert "<h1>Title</h1>" in html
    assert "<h2>Subtitle</h2>" in html


def test_lists_render():
    html = render_content_block_markdown("- a\n- b\n- c")
    assert "<ul>" in html
    assert "<li>a</li>" in html


def test_links_render_with_rel():
    html = render_content_block_markdown("[example](https://example.com)")
    assert 'href="https://example.com"' in html
    assert 'rel="noopener noreferrer"' in html


def test_images_render():
    html = render_content_block_markdown("![alt](https://example.com/img.png)")
    assert "<img" in html
    assert 'src="https://example.com/img.png"' in html
    assert 'alt="alt"' in html


# --- XSS vectors stripped ---------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        '<script>alert("xss")</script>',
        '<img src="x" onerror="alert(1)">',
        '<a href="javascript:alert(1)">click</a>',
        '<a href="data:text/html,<script>alert(1)</script>">click</a>',
        '<iframe src="https://evil.com"></iframe>',
        '<form action="https://evil.com"><input type="submit"></form>',
        '<svg onload="alert(1)">',
        "<style>body{background:url(javascript:alert(1))}</style>",
        '<div onclick="alert(1)">text</div>',
        '<a href="vbscript:msgbox(1)">click</a>',
    ],
)
def test_xss_vectors_stripped(payload):
    """Dangerous HTML in the Markdown source must not survive sanitisation."""
    html = render_content_block_markdown(payload)
    # No event-handler attributes.
    assert "onerror" not in html
    assert "onclick" not in html
    assert "onload" not in html
    # No dangerous tags.
    assert "<script" not in html
    assert "<iframe" not in html
    assert "<form" not in html
    assert "<style" not in html
    assert "<svg" not in html
    # No dangerous schemes.
    assert "javascript:" not in html
    assert "vbscript:" not in html
    assert "data:text/html" not in html


def test_script_after_markdown_stripped():
    """A payload that Markdown converts to valid HTML must still be cleaned."""
    md = '![img](https://example.com/x.png)\n\n<script>alert("xss")</script>'
    html = render_content_block_markdown(md)
    assert "<script" not in html
    assert "alert" not in html


def test_html_comment_stripped():
    html = render_content_block_markdown("<!-- conditional comment -->\n\ntext")
    assert "<!--" not in html


# --- URL scheme allowlist ---------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("mailto:foo@example.com", "mailto:foo@example.com"),
        ("/relative/path", "/relative/path"),
        ("relative/path", "relative/path"),
        ("javascript:alert(1)", ""),
        ("data:text/html,<script>", ""),
        ("vbscript:msgbox(1)", ""),
        ("file:///etc/passwd", ""),
        ("", ""),
        ("   ", ""),
    ],
)
def test_sanitise_link_url(url, expected):
    assert sanitise_link_url(url) == expected


def test_protocol_relative_url_blocked():
    # //evil.com is protocol-relative — should be blocked because it
    # inherits the page scheme and could resolve to an attacker host.
    assert sanitise_link_url("//evil.com") == ""
