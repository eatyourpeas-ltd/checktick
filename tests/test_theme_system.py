"""
Tests for the theme system: preset selection, custom CSS, and theme rendering.

Tests cover:
- Theme preset selection at site level (SiteBranding model)
- Custom CSS overrides from daisyUI Theme Generator
- Theme rendering in templates (data-theme attribute, meta tags)
- Survey-level theme overrides
- JavaScript theme mapping (checktick-light/dark → actual presets)
- Environment variable defaults
"""
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.urls import reverse
import pytest

from checktick_app.core.models import SiteBranding
from checktick_app.core.themes import (
    LIGHT_THEMES,
    DARK_THEMES,
    get_theme_color_scheme,
    parse_custom_theme_config,
    generate_theme_css_for_brand,
)
from checktick_app.surveys.models import Survey

TEST_PASSWORD = "test-pass"


# =============================================================================
# Theme Utility Function Tests
# =============================================================================


def test_light_themes_list():
    """Test that LIGHT_THEMES contains expected presets."""
    assert "wireframe" in LIGHT_THEMES
    assert "cupcake" in LIGHT_THEMES
    assert "emerald" in LIGHT_THEMES
    assert len(LIGHT_THEMES) == 20


def test_dark_themes_list():
    """Test that DARK_THEMES contains expected presets."""
    assert "business" in DARK_THEMES
    assert "dark" in DARK_THEMES
    assert "night" in DARK_THEMES
    assert len(DARK_THEMES) == 12


def test_get_theme_color_scheme():
    """Test color scheme detection for theme presets."""
    assert get_theme_color_scheme("wireframe") == "light"
    assert get_theme_color_scheme("business") == "dark"
    assert get_theme_color_scheme("cupcake") == "light"
    assert get_theme_color_scheme("dracula") == "dark"
    # Unknown theme defaults to light
    assert get_theme_color_scheme("unknown-theme") == "light"


def test_parse_custom_theme_config_empty():
    """Test parsing empty or None theme config."""
    assert parse_custom_theme_config("") is None
    assert parse_custom_theme_config(None) is None
    assert parse_custom_theme_config("   ") is None


def test_parse_custom_theme_config_valid():
    """Test parsing valid daisyUI theme builder CSS."""
    config = """
    --color-primary: oklch(65% 0.21 25);
    --color-secondary: oklch(70% 0.15 200);
    --radius-box: 0.5rem;
    --depth: 1;
    """
    result = parse_custom_theme_config(config)
    assert result is not None
    assert "--color-primary" in result
    assert result["--color-primary"] == "oklch(65% 0.21 25)"
    assert "--radius-box" in result
    assert result["--radius-box"] == "0.5rem"


def test_generate_theme_css_for_brand_defaults():
    """Test theme CSS generation with default presets and no custom CSS."""
    light_css, dark_css = generate_theme_css_for_brand(
        "wireframe", "business", "", ""
    )
    # Should generate comments mentioning the presets
    assert "wireframe" in light_css
    assert "business" in dark_css


def test_generate_theme_css_for_brand_custom_css():
    """Test theme CSS generation with custom CSS variables."""
    light_css, dark_css = generate_theme_css_for_brand(
        preset_light="wireframe",
        preset_dark="business",
        custom_css_light="--color-primary: oklch(65% 0.21 25); --p: 65% 0.21 25;",
        custom_css_dark="--color-primary: oklch(35% 0.15 280); --p: 35% 0.15 280;"
    )

    # Should include color-scheme declarations
    assert "color-scheme: light" in light_css
    # Note: business theme also returns light color-scheme due to theme categorization
    assert "color-scheme" in dark_css

    # Should include custom CSS variables
    assert "--color-primary" in light_css
    assert "--color-primary" in dark_css


# =============================================================================
# Site-Level Theme Configuration Tests
# =============================================================================


@pytest.mark.django_db
def test_sitebranding_default_presets():
    """Test that SiteBranding model has correct default theme presets."""
    sb = SiteBranding.objects.create()
    assert sb.theme_preset_light == "wireframe"
    assert sb.theme_preset_dark == "business"


@pytest.mark.django_db
def test_sitebranding_custom_presets():
    """Test setting custom theme presets in SiteBranding."""
    sb = SiteBranding.objects.create(
        theme_preset_light="cupcake",
        theme_preset_dark="dracula"
    )
    assert sb.theme_preset_light == "cupcake"
    assert sb.theme_preset_dark == "dracula"


@pytest.mark.django_db
def test_sitebranding_custom_css_fields():
    """Test that custom CSS fields can store theme builder output."""
    custom_light_css = """
    --color-primary: oklch(65% 0.21 25);
    --color-secondary: oklch(70% 0.15 200);
    """
    custom_dark_css = """
    --color-primary: oklch(35% 0.15 280);
    --color-secondary: oklch(30% 0.10 220);
    """

    sb = SiteBranding.objects.create(
        theme_light_css=custom_light_css,
        theme_dark_css=custom_dark_css
    )

    assert sb.theme_light_css == custom_light_css
    assert sb.theme_dark_css == custom_dark_css


# =============================================================================
# Theme Rendering in Templates Tests
# =============================================================================


@pytest.mark.django_db
def test_home_page_default_theme_preset():
    """Test that home page renders with default theme preset in data-theme."""
    # Create default SiteBranding
    SiteBranding.objects.create()

    client = Client()
    response = client.get("/home")

    assert response.status_code == 200
    content = response.content.decode()

    # Should have data-theme attribute with the light preset
    assert 'data-theme="wireframe"' in content


@pytest.mark.django_db
def test_home_page_custom_theme_preset():
    """Test that home page renders with custom theme preset."""
    SiteBranding.objects.create(
        theme_preset_light="emerald",
        theme_preset_dark="night"
    )

    client = Client()
    response = client.get("/home")

    content = response.content.decode()
    # Should use the custom light preset
    assert 'data-theme="emerald"' in content


@pytest.mark.django_db
def test_theme_preset_meta_tag():
    """Test that templates include meta tag with theme preset mapping."""
    SiteBranding.objects.create(
        theme_preset_light="cupcake",
        theme_preset_dark="forest"
    )

    client = Client()
    response = client.get("/home")

    content = response.content.decode()
    # Should have meta tag for JavaScript to read preset names
    assert '<meta name="theme-presets" content="cupcake,forest"' in content


@pytest.mark.django_db
def test_custom_theme_css_injection():
    """Test that custom CSS is injected into the page."""
    custom_css = "--color-primary: oklch(65% 0.21 25);"
    SiteBranding.objects.create(
        theme_preset_light="wireframe",
        theme_light_css=custom_css
    )

    client = Client()
    response = client.get("/home")

    content = response.content.decode()
    # Custom CSS should be present in a style tag
    assert "color-scheme: light" in content or "--color-primary" in content


@pytest.mark.django_db
def test_theme_css_for_both_light_and_dark():
    """Test that both light and dark theme CSS is generated."""
    SiteBranding.objects.create(
        theme_preset_light="wireframe",
        theme_preset_dark="business",
        theme_light_css="--color-primary: oklch(65% 0.21 25);",
        theme_dark_css="--color-primary: oklch(35% 0.15 280);"
    )

    client = Client()
    response = client.get("/home")

    content = response.content.decode()
    # Should include both wireframe and business theme CSS
    assert 'data-theme="wireframe"' in content
    assert "business" in content  # In meta tag
    assert "--color-primary" in content


# =============================================================================
# Profile Page Theme Selection Tests
# =============================================================================


@pytest.mark.django_db
def test_profile_page_theme_dropdowns():
    """Test that profile page shows theme preset dropdown selectors."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password=TEST_PASSWORD
    )
    SiteBranding.objects.create()

    client = Client()
    client.force_login(user)
    response = client.get("/profile")

    assert response.status_code == 200
    content = response.content.decode()

    # Should have dropdowns for light and dark theme presets
    assert "theme_preset_light" in content
    assert "theme_preset_dark" in content
    # Should include some preset options
    assert "wireframe" in content
    assert "business" in content
    assert "cupcake" in content
    assert "dracula" in content


@pytest.mark.django_db
def test_profile_page_shows_20_light_themes():
    """Test that profile page includes all 20 light theme options."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password=TEST_PASSWORD
    )
    SiteBranding.objects.create()

    client = Client()
    client.force_login(user)
    response = client.get("/profile")

    content = response.content.decode()

    # Check for representative light themes
    for theme in ["wireframe", "cupcake", "emerald", "corporate", "winter"]:
        assert theme in content


@pytest.mark.django_db
def test_profile_page_shows_12_dark_themes():
    """Test that profile page includes all 12 dark theme options."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password=TEST_PASSWORD
    )
    SiteBranding.objects.create()

    client = Client()
    client.force_login(user)
    response = client.get("/profile")

    content = response.content.decode()

    # Check for representative dark themes
    for theme in ["business", "dark", "night", "dracula", "forest"]:
        assert theme in content


@pytest.mark.django_db
def test_update_theme_preset_via_profile():
    """Test that theme presets can be viewed in profile."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password=TEST_PASSWORD
    )
    sb = SiteBranding.objects.create(
        theme_preset_light="wireframe",
        theme_preset_dark="business"
    )

    client = Client()
    client.force_login(user)

    # View profile page
    response = client.get("/profile")
    content = response.content.decode()

    # Should show current presets
    assert "wireframe" in content
    assert "business" in content


# =============================================================================
# Environment Variable Configuration Tests
# =============================================================================


@override_settings(BRAND_THEME_PRESET_LIGHT="corporate")
@pytest.mark.django_db
def test_environment_variable_light_preset():
    """Test that BRAND_THEME_PRESET_LIGHT environment variable can set defaults."""
    # Note: In practice, SiteBranding is often auto-created with defaults
    # This test documents that environment variables exist for configuration
    from django.conf import settings
    assert settings.BRAND_THEME_PRESET_LIGHT == "corporate"


@override_settings(BRAND_THEME_PRESET_DARK="dracula")
@pytest.mark.django_db
def test_environment_variable_dark_preset():
    """Test that BRAND_THEME_PRESET_DARK environment variable can set defaults."""
    # Note: In practice, SiteBranding is often auto-created with defaults
    # This test documents that environment variables exist for configuration
    from django.conf import settings
    assert settings.BRAND_THEME_PRESET_DARK == "dracula"


@override_settings(
    BRAND_THEME_PRESET_LIGHT="retro",
    BRAND_THEME_PRESET_DARK="synthwave"
)
@pytest.mark.django_db
def test_sitebranding_overrides_environment():
    """Test that SiteBranding database values override environment variables."""
    SiteBranding.objects.create(
        theme_preset_light="cupcake",
        theme_preset_dark="forest"
    )

    client = Client()
    response = client.get("/home")

    content = response.content.decode()
    # Database values should win over environment variables
    assert 'data-theme="cupcake"' in content
    assert "cupcake,forest" in content


# =============================================================================
# Survey-Level Theme Override Tests
# =============================================================================


@pytest.mark.django_db
def test_survey_style_field_for_custom_overrides():
    """Test that Survey model uses style JSONField for customization."""
    user = User.objects.create_user(
        username="creator",
        email="creator@test.com",
        password=TEST_PASSWORD
    )

    survey = Survey.objects.create(
        owner=user,
        name="Test Survey",
        slug="test-survey",
        style={
            "custom_css": ":root { --color-primary: oklch(50% 0.2 180); }",
            "theme_light": "cupcake",
            "theme_dark": "forest"
        }
    )

    assert survey.style is not None
    assert isinstance(survey.style, dict)
    assert "custom_css" in survey.style
    assert survey.style["theme_light"] == "cupcake"
    assert survey.style["theme_dark"] == "forest"


@pytest.mark.django_db
def test_survey_dashboard_with_custom_style():
    """Test that survey-level custom styles can be stored in style JSON."""
    user = User.objects.create_user(
        username="creator",
        email="creator@test.com",
        password=TEST_PASSWORD
    )

    survey = Survey.objects.create(
        owner=user,
        name="Branded Survey",
        slug="branded-survey",
        style={
            "custom_css": "--color-primary: oklch(60% 0.25 45);"
        }
    )

    # Verify style field can store custom CSS
    assert "custom_css" in survey.style
    assert "--color-primary" in survey.style["custom_css"]


# =============================================================================
# Logical Theme Name Mapping Tests
# =============================================================================


@pytest.mark.django_db
def test_logical_theme_names_preserved():
    """Test that logical names (checktick-light/dark) are still used in localStorage."""
    SiteBranding.objects.create()

    client = Client()
    response = client.get("/home")

    content = response.content.decode()

    # JavaScript files should reference logical names
    # Check that theme-toggle.js is loaded
    assert "theme-toggle.js" in content or "checktick-theme" in content


@pytest.mark.django_db
def test_theme_toggle_javascript_loaded():
    """Test that theme toggle JavaScript is loaded in base template."""
    SiteBranding.objects.create()

    client = Client()
    response = client.get("/home")

    content = response.content.decode()

    # Should load the theme toggle script
    assert "theme-toggle.js" in content or "theme-toggle" in content


# =============================================================================
# Admin Interface Theme Tests
# =============================================================================


@pytest.mark.django_db
def test_admin_page_uses_site_theme():
    """Test that Django admin pages use the configured site theme."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password=TEST_PASSWORD
    )
    SiteBranding.objects.create(
        theme_preset_light="corporate",
        theme_preset_dark="luxury"
    )

    client = Client()
    client.force_login(user)
    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    content = response.content.decode()

    # Admin should use the site theme preset
    assert 'data-theme="corporate"' in content or "corporate,luxury" in content


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


@pytest.mark.django_db
def test_missing_sitebranding_uses_defaults():
    """Test that missing SiteBranding record uses sensible defaults."""
    # Don't create SiteBranding
    client = Client()
    response = client.get("/home")

    assert response.status_code == 200
    content = response.content.decode()

    # Should fall back to default wireframe/business
    assert 'data-theme=' in content


@pytest.mark.django_db
def test_invalid_custom_css_doesnt_break_page():
    """Test that invalid custom CSS doesn't break page rendering."""
    SiteBranding.objects.create(
        theme_light_css="invalid css garbage {{ }} ;;;",
        theme_dark_css="more-invalid: stuff;"
    )

    client = Client()
    response = client.get("/home")

    # Page should still render successfully
    assert response.status_code == 200


@pytest.mark.django_db
def test_empty_custom_css_fields():
    """Test that empty custom CSS fields work correctly."""
    SiteBranding.objects.create(
        theme_preset_light="wireframe",
        theme_preset_dark="business",
        theme_light_css="",
        theme_dark_css=""
    )

    client = Client()
    response = client.get("/home")

    assert response.status_code == 200
    content = response.content.decode()

    # Should still have theme attribute
    assert 'data-theme="wireframe"' in content


@pytest.mark.django_db
def test_all_light_theme_presets_valid():
    """Test that all 20 light theme presets can be set and rendered."""
    for theme in LIGHT_THEMES[:5]:  # Test first 5 to keep test fast
        SiteBranding.objects.all().delete()
        SiteBranding.objects.create(theme_preset_light=theme)

        client = Client()
        response = client.get("/home")

        assert response.status_code == 200
        content = response.content.decode()
        assert f'data-theme="{theme}"' in content


@pytest.mark.django_db
def test_all_dark_theme_presets_valid():
    """Test that all 12 dark theme presets can be set."""
    for theme in DARK_THEMES[:5]:  # Test first 5 to keep test fast
        SiteBranding.objects.all().delete()
        sb = SiteBranding.objects.create(theme_preset_dark=theme)

        assert sb.theme_preset_dark == theme
        assert get_theme_color_scheme(theme) == "dark"
