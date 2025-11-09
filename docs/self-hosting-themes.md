# Self-Hosting: Platform Theme Configuration

This guide covers platform-level theme configuration for self-hosted CheckTick deployments. These settings control the default appearance for all users and can be overridden by organization owners.

## Overview

CheckTick uses a **3-tier theme hierarchy**:

1. **Platform defaults** (this guide) - Set by deployment admin via environment variables and Django admin
2. **Organization themes** - Set by organization owners via Profile page (see [Branding and Theme Settings](branding-and-theme-settings.md))
3. **Survey themes** - Set by survey creators for individual surveys

This guide focuses on **platform-level configuration** for deployment administrators.

## Platform Theme Environment Variables

Set these environment variables in your deployment configuration (e.g., `.env` file, Docker Compose, Kubernetes secrets).

### Branding Variables

```bash
# Site title (shown in navbar and browser tab)
BRAND_TITLE="CheckTick"

# Icon URLs (optional - can also upload via Django admin)
BRAND_ICON_URL="/static/icons/checktick_brand_favicon.svg"
BRAND_ICON_URL_DARK="/static/icons/checktick_brand_favicon_dark.svg"

# Icon accessibility
BRAND_ICON_ALT="CheckTick"
BRAND_ICON_TITLE="CheckTick"

# Icon size (Tailwind classes or numeric)
BRAND_ICON_SIZE_CLASS="w-6 h-6"
# OR
BRAND_ICON_SIZE=6  # Converts to w-6 h-6
```

### Theme Preset Variables

CheckTick uses **daisyUI v5.4.7** with 32 built-in theme presets:

```bash
# Default logical theme (checktick-light or checktick-dark)
BRAND_THEME="checktick-light"

# Light mode preset (default: nord)
# Available: light, cupcake, bumblebee, emerald, corporate, retro, 
# cyberpunk, valentine, garden, lofi, pastel, fantasy, nord, 
# cmyk, autumn, acid, lemonade, winter, nord, sunset
BRAND_THEME_PRESET_LIGHT="nord"

# Dark mode preset (default: business)
# Available: dark, synthwave, halloween, forest, aqua, black, 
# luxury, dracula, business, night, coffee, dim
BRAND_THEME_PRESET_DARK="business"
```

### Font Variables

```bash
# Heading font stack
BRAND_FONT_HEADING="'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'"

# Body font stack
BRAND_FONT_BODY="Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif"

# Optional external font CSS URL
BRAND_FONT_CSS_URL="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap"
```

### Advanced: Custom Theme CSS

For advanced deployments requiring custom brand colors beyond presets:

```bash
# Custom CSS variables for light theme (from daisyUI Theme Generator)
BRAND_THEME_CSS_LIGHT="--color-primary: oklch(65% 0.21 25); --radius-selector: 1rem;"

# Custom CSS variables for dark theme
BRAND_THEME_CSS_DARK="--color-primary: oklch(45% 0.18 25); --radius-selector: 1rem;"
```

**Note**: Most deployments should use preset themes only. Custom CSS requires understanding of [daisyUI Theme Generator](https://daisyui.com/theme-generator/) variables.

## Django Admin Configuration

Platform administrators (superusers) can also configure themes via the Django admin interface, which overrides environment variables.

### Accessing SiteBranding Admin

1. Log in as a superuser
2. Navigate to `/admin/`
3. Click on **Site Branding** under Core

### SiteBranding Model Fields

The admin interface provides access to all platform theme settings:

**Theme Presets:**
- `default_theme` - Logical theme name (checktick-light/checktick-dark)
- `theme_preset_light` - daisyUI preset for light mode (dropdown with 20 options)
- `theme_preset_dark` - daisyUI preset for dark mode (dropdown with 12 options)

**Icons:**
- `icon_file` - Upload light mode icon (SVG/PNG)
- `icon_url` - Or provide URL for light mode icon
- `icon_file_dark` - Upload dark mode icon (optional)
- `icon_url_dark` - Or provide URL for dark mode icon

**Fonts:**
- `font_heading` - CSS font stack for headings
- `font_body` - CSS font stack for body text
- `font_css_url` - External font CSS URL (e.g., Google Fonts)

**Advanced Custom CSS:**
- `theme_light_css` - Custom CSS variables for light theme
- `theme_dark_css` - Custom CSS variables for dark theme

### Field Precedence

When both environment variables and database values exist:

1. **Database values** (SiteBranding model) - highest priority
2. **Environment variables** - fallback
3. **Built-in defaults** - last resort

This allows deployments to set sensible defaults via environment while allowing runtime customization through the admin.

## CSS Build Process

CheckTick uses **Tailwind CSS v4** with CSS-based configuration (no `tailwind.config.js`).

### When to Rebuild CSS

Rebuild CSS when you:
- Change Tailwind/daisyUI configuration in CSS files
- Add new templates with utility classes
- Update custom theme CSS
- Modify component styles

### How to Rebuild

**In development (Docker):**
```bash
docker compose exec web npm run build:css
```

**In production (local):**
```bash
npm run build:css
```

**Build details:**
- Input: `checktick_app/static/css/daisyui_themes.css`
- Output: `checktick_app/static/build/styles.css` (minified)
- Build time: ~250ms
- Output size: ~192KB (includes all 39 daisyUI themes)

### Tailwind v4 Architecture

Key differences from Tailwind v3:

- **No JavaScript config file** - Uses `@import`, `@plugin`, `@theme` directives in CSS
- **Separate CLI package** - Uses `@tailwindcss/cli` instead of main package
- **CSS-first configuration** - All config in `daisyui_themes.css`

Configuration example:
```css
@import "tailwindcss";
@plugin "daisyui" { 
  themes: all;  /* Loads all 39 themes */
}
@plugin "@tailwindcss/typography";
```

## Theme Architecture

### Logical vs Physical Theme Names

CheckTick uses a **logical naming system** to separate user preferences from actual daisyUI presets:

**Logical names** (stored in user preferences):
- `checktick-light` - User's light mode preference
- `checktick-dark` - User's dark mode preference
- `system` - Follow OS preference

**Physical names** (actual daisyUI presets applied to DOM):
- `nord`, `business`, `cupcake`, etc.
- Applied via `<html data-theme="nord">`

**Why?** This allows changing the platform's default light/dark themes without breaking user preferences. Users who selected "light mode" will automatically get the new light preset.

### How Theme Selection Works

1. **User preference** stored in browser localStorage (`checktick-theme`)
2. **JavaScript** (`theme-toggle.js`) maps logical name to physical preset
3. **Platform config** determines which preset each logical name maps to
4. **DOM updated** with `<html data-theme="nord">` (physical name)

### Theme Cascade Logic

The context processor (`context_processors.py`) implements the cascade:

```python
# Check for organization theme
if user_org and (user_org.theme_preset_light or user_org.theme_preset_dark):
    # Use organization theme
    preset_light = user_org.theme_preset_light
    preset_dark = user_org.theme_preset_dark
else:
    # Fall back to platform theme
    preset_light = platform_preset_light
    preset_dark = platform_preset_dark
```

**Result:** Organization members see their org's custom theme, while users without an organization see platform defaults.

## Custom Theme CSS

For deployments requiring brand-specific colors beyond presets, use the [daisyUI Theme Generator](https://daisyui.com/theme-generator/).

### Using the Theme Generator

1. Visit [daisyui.com/theme-generator](https://daisyui.com/theme-generator/)
2. Customize colors, border radius, etc.
3. Copy the generated CSS variables
4. Paste into `BRAND_THEME_CSS_LIGHT` and `BRAND_THEME_CSS_DARK`

### Acceptable CSS Format

Only paste **CSS variable declarations**:

```css
--color-primary: oklch(65% 0.21 25);
--color-secondary: oklch(70% 0.15 200);
--radius-selector: 1rem;
--depth: 0;
```

**Do not paste:**
- CSS selectors (`:root`, `[data-theme="..."]`)
- Rule blocks with `{ }`
- Arbitrary CSS rules

The system automatically normalizes and injects variables under the correct theme selectors.

### How Custom CSS Works

1. **Generator variables** normalized to daisyUI runtime variables
2. **Injected** into `<style>` block in page `<head>`
3. **Applied** under `[data-theme="checktick-light"]` and `[data-theme="checktick-dark"]`
4. **Merged** with base preset (custom variables override preset values)

## Production Deployment

### Docker Environment Variables

In `docker-compose.yml` or `.env`:

```yaml
environment:
  - BRAND_TITLE=MyOrganization CheckTick
  - BRAND_THEME_PRESET_LIGHT=corporate
  - BRAND_THEME_PRESET_DARK=luxury
  - BRAND_ICON_URL=/static/icons/custom-logo.svg
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: checktick-config
data:
  BRAND_TITLE: "MyOrganization CheckTick"
  BRAND_THEME_PRESET_LIGHT: "corporate"
  BRAND_THEME_PRESET_DARK: "luxury"
```

### Static Files

After changing themes, collect static files in production:

```bash
python manage.py collectstatic --noinput
```

In Docker:
```bash
docker compose exec web python manage.py collectstatic --noinput
```

## Security Considerations

### Superuser-Only Access

- Only superusers can access `/admin/` and modify SiteBranding
- Regular users cannot change platform defaults
- Organization owners can only theme their own organization
- Survey creators can only theme their own surveys

### CSS Injection Protection

- Custom CSS fields are **sanitized** to prevent XSS
- Only CSS variable declarations are accepted
- JavaScript and external resources are blocked
- Validation occurs on save

### Icon Upload Security

- File type validation (SVG, PNG, JPG, WebP only)
- File size limits enforced
- Files stored in MEDIA_ROOT with restricted permissions
- Served via Django's media URL (not executable)

## Troubleshooting

### Theme Not Applying

**Check precedence:**
1. Database SiteBranding overrides environment variables
2. Organization themes override platform defaults
3. Survey themes override organization themes

**Clear caches:**
```bash
# Browser localStorage
localStorage.removeItem('checktick-theme')

# Django cache (if using)
docker compose exec web python manage.py clear_cache
```

### Custom CSS Not Working

**Verify format:**
- Only variable declarations allowed
- No CSS selectors or rule blocks
- Check browser DevTools console for errors

**Rebuild CSS:**
```bash
docker compose exec web npm run build:css
```

### Icons Not Showing

**Check file paths:**
- Uploaded files: `/media/icons/...`
- Static files: `/static/icons/...`
- External URLs: Must be absolute and accessible

**Verify media configuration:**
```python
# settings.py
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### Colors Look Wrong

**Check theme preset:**
- Verify `BRAND_THEME_PRESET_LIGHT` and `BRAND_THEME_PRESET_DARK`
- Ensure preset name matches daisyUI options
- Test both light and dark modes

**Check custom CSS:**
- Verify OKLCH color values (not hex)
- Ensure percentage and decimal formats correct
- Test in daisyUI Theme Generator first

## Related Documentation

- [Branding and Theme Settings](branding-and-theme-settings.md) - User guide for theme hierarchy and organization-level theming
- [Themes](themes.md) - Technical implementation details for developers
- [Self-Hosting Configuration](self-hosting-configuration.md) - General deployment configuration

## Support

For deployment assistance:
- Check [Getting Help](getting-help.md)
- Review [Issues vs Discussions](issues-vs-discussions.md)
- Join community discussions on GitHub
