---
title: Themes (Legacy)
category: configuration
priority: 2
---

This guide covers the technical implementation of CheckTick's theming system for developers. For user-facing theme configuration, see [Branding and Theme Settings](branding-and-theme-settings.md). For platform deployment configuration, see [Self-Hosting: Platform Theme Configuration](self-hosting-themes.md).

**Note:** Platform-level branding configuration (logos, themes, fonts) is available to:

- Enterprise tier users on hosted CheckTick (via `/branding/` web UI)
- Superusers on self-hosted deployments (via web UI or `manage.py configure_branding` CLI)

## Technology Stack

- **Tailwind CSS v4.1.17** - Utility-first CSS framework with CSS-based configuration
- **daisyUI v5.4.7** - Component library with 32 built-in theme presets
- **@tailwindcss/typography** - Rich text styling for prose content
- **@tailwindcss/cli v4.1.17** - Separate build tool package for Tailwind v4

## Tailwind CSS v4 Configuration

Tailwind CSS v4 uses **CSS-based configuration** instead of JavaScript config files:

- **Entry point**: `checktick_app/static/css/daisyui_themes.css`
- **Configuration**: Uses `@import`, `@plugin`, and `@theme` directives in CSS
- **Build tool**: `@tailwindcss/cli` v4.1.17 (separate package from Tailwind)
- **No `tailwind.config.js`**: All configuration is in CSS files

Example configuration structure:

```css
@import "tailwindcss";
@plugin "daisyui" { themes: all; }
@plugin "@tailwindcss/typography";
```

### Key Differences from Tailwind v3

1. **CSS-first configuration** - No JavaScript config file required
2. **Separate CLI package** - `@tailwindcss/cli` instead of `tailwindcss` CLI
3. **New `@` directives** - `@import`, `@plugin`, `@theme`, `@source`
4. **Native CSS features** - Better integration with modern CSS

## daisyUI v5 Themes

All 32 daisyUI themes are loaded in CheckTick:

**20 Light Themes:**

- light, cupcake, bumblebee, emerald, corporate, retro, cyberpunk, valentine, garden, lofi, pastel, fantasy, nord, cmyk, autumn, acid, lemonade, winter, nord, sunset

**12 Dark Themes:**

- dark, synthwave, halloween, forest, aqua, black, luxury, dracula, business, night, coffee, dim

Themes are applied via the `data-theme` attribute on `<html>` or `<body>`:

```html
<html data-theme="corporate">
```

### Logical Naming System

CheckTick uses a **logical naming system** to separate user preferences from actual daisyUI presets:

- **checktick-light** (logical name) → maps to selected light preset (default: "pastel")
- **checktick-dark** (logical name) → maps to selected dark preset (default: "dim")
- JavaScript automatically applies the correct daisyUI preset based on configuration

**Why?** This allows changing platform default themes without breaking user preferences. A user who selected "light mode" will automatically get the new light preset if the platform admin changes it.

## Theme Architecture

### File Structure

```console
checktick_app/
├── static/
│   ├── css/
│   │   └── daisyui_themes.css      # Tailwind v4 entry point
│   ├── build/
│   │   └── styles.css               # Built output (minified)
│   └── js/
│       ├── theme-toggle.js          # User theme switcher
│       └── admin-theme.js           # Admin theme switcher
├── core/
│   ├── themes.py                    # Theme utilities (presets, parsing)
│   ├── models.py                    # SiteBranding model
│   └── views.py                     # Theme update handlers
├── surveys/
│   └── models.py                    # Organisation, Survey models
├── context_processors.py            # Theme cascade logic
└── templates/
    ├── base.html                    # Main template with theme
    ├── base_minimal.html            # Minimal template
    └── admin/
        └── base_site.html           # Admin template override
```

### Theme Cascade Logic

The context processor (`checktick_app/context_processors.py`) implements the 3-tier hierarchy:

```python
# 1. Start with platform defaults (environment vars + SiteBranding)
preset_light = settings.BRAND_THEME_PRESET_LIGHT or "corporate"
preset_dark = settings.BRAND_THEME_PRESET_DARK or "business"

if SiteBranding:
    sb = SiteBranding.objects.first()
    if sb:
        preset_light = sb.theme_preset_light or preset_light
        preset_dark = sb.theme_preset_dark or preset_dark

# 2. Check for organisation-level override
user_org = None
if user and user.is_authenticated:
    # Get user's primary organisation
    user_org = Organization.objects.filter(owner=user).first()
    if not user_org:
        membership = OrganizationMembership.objects.filter(user=user).first()
        if membership:
            user_org = membership.organization

# 3. Apply organisation theme if set
if user_org and (user_org.theme_preset_light or user_org.theme_preset_dark):
    preset_light = user_org.theme_preset_light or preset_light
    preset_dark = user_org.theme_preset_dark or preset_dark
    # Also apply custom CSS if provided
    if user_org.theme_light_css:
        theme_css_light = user_org.theme_light_css
    if user_org.theme_dark_css:
        theme_css_dark = user_org.theme_dark_css

# 4. Survey-level overrides handled per-template (not in context processor)
```

### Database Models

**SiteBranding** (platform-level):

```python
class SiteBranding(models.Model):
    default_theme = models.CharField(max_length=64)  # checktick-light/dark
    theme_preset_light = models.CharField(max_length=64)  # corporate, etc.
    theme_preset_dark = models.CharField(max_length=64)   # business, etc.
    theme_light_css = models.TextField()  # Custom CSS variables
    theme_dark_css = models.TextField()   # Custom CSS variables
    icon_file = models.FileField()        # Uploaded icon
    icon_url = models.URLField()          # Or icon URL
    # ... font fields, dark mode icon fields
```

**Organisation** (organisation-level):

```python
class Organisation(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User)
    default_theme = models.CharField(max_length=64, blank=True)
    theme_preset_light = models.CharField(max_length=64, blank=True)
    theme_preset_dark = models.CharField(max_length=64, blank=True)
    theme_light_css = models.TextField(blank=True)
    theme_dark_css = models.TextField(blank=True)
```

**Survey** (survey-level):

```python
class Survey(models.Model):
    owner = models.ForeignKey(User)
    organisation = models.ForeignKey(Organisation, null=True, blank=True)
    style = models.JSONField(default=dict)  # Flexible styling
    # style structure:
    # {
    #   "custom_css": "...",
    #   "theme_light": "cupcake",
    #   "theme_dark": "forest",
    #   "fonts": {...}
    # }
```

## CSS Build Process

### Build Configuration

**package.json** script:
```json
{
  "scripts": {
    "build:css": "tailwindcss --input checktick_app/static/css/daisyui_themes.css --output checktick_app/static/build/styles.css --minify"
  }
}
```

### Build Details

- **Input**: `checktick_app/static/css/daisyui_themes.css`
- **Output**: `checktick_app/static/build/styles.css` (minified)
- **Build time**: ~250ms
- **Output size**: ~192KB (includes all 39 daisyUI themes)
- **Watch mode**: `npm run build:css -- --watch`

### When to Rebuild

Rebuild CSS when:

- Changing Tailwind/daisyUI configuration in CSS files
- Adding new templates with utility classes
- Modifying component styles in CSS
- Updating `@plugin` or `@theme` directives

**Development (Docker):**

```bash
docker compose exec web npm run build:css
```

**Production:**

```bash
npm run build:css
python manage.py collectstatic --noinput
```

## Theme Utilities

### themes.py Module

Location: `checktick_app/core/themes.py`

**Constants:**

```python
LIGHT_THEMES = [
    "light", "cupcake", "bumblebee", "emerald", "corporate", "retro",
    "cyberpunk", "valentine", "garden", "lofi", "pastel", "fantasy",
    "nord", "cmyk", "autumn", "acid", "lemonade", "winter", "nord", "sunset"
]

DARK_THEMES = [
    "dark", "synthwave", "halloween", "forest", "aqua", "black",
    "luxury", "dracula", "business", "night", "coffee", "dim"
]
```

**Functions:**

`get_theme_color_scheme(theme_name: str) -> str`

- Returns "light" or "dark" for a given theme preset name
- Used to determine appropriate meta tags and prefers-color-scheme

`normalize_daisyui_builder_css(raw_css: str) -> str`

- Normalizes CSS from daisyUI Theme Generator
- Strips selectors, extracts variables only
- Maps builder variables to daisyUI runtime variables

`generate_theme_css_for_brand(preset_light, preset_dark, custom_light_css, custom_dark_css) -> tuple`

- Generates complete theme CSS for both modes
- Merges preset with custom CSS overrides
- Returns `(light_css, dark_css)` tuple
- Used by SiteBranding and Organisation models

`parse_custom_theme_config(config: dict) -> dict`

- Parses survey `style` JSONField
- Extracts theme presets, custom CSS, fonts
- Returns normalized configuration dict

### Example Usage

```python
from checktick_app.core.themes import (
    LIGHT_THEMES,
    get_theme_color_scheme,
    generate_theme_css_for_brand
)

# Check theme color scheme
scheme = get_theme_color_scheme("corporate")  # "light"

# Generate theme CSS
light_css, dark_css = generate_theme_css_for_brand(
    preset_light="pastel",
    preset_dark="dim",
    custom_light_css="--color-primary: oklch(65% 0.21 25);",
    custom_dark_css="--color-primary: oklch(45% 0.18 25);"
)
```

## Project-Level vs Organisation-Level vs Survey-Level Theming

### 1. Platform-Level (Global)

- Who: Organisation admin (superuser) in the Profile page
- Applies to: Entire site by default
- What you can configure:
  - **Theme presets**: Choose from 20 light themes and 12 dark themes (daisyUI v5.4.7 presets)
    - Default light: `nord` (clean, minimal design)
    - Default dark: `business` (professional dark theme)
    - Can be changed via dropdown selectors in Profile page
  - **Advanced custom CSS**: Optional custom theme CSS from the [daisyUI Theme Generator](https://daisyui.com/theme-generator/) that overrides the selected presets
  - Site icon (favicon): upload SVG/PNG or provide a URL
  - Dark-mode icon: upload a separate SVG/PNG or provide a URL (used when the dark theme is active)
  - Fonts: heading/body stacks and an optional external Font CSS URL (e.g. Google Fonts)
- Where it's stored: `SiteBranding` model in the database (`theme_preset_light`, `theme_preset_dark`, `theme_css_light`, `theme_css_dark`)
- How it's applied:
  - The base template (`base.html`) uses the configured presets in the `data-theme` attribute
  - The logical theme names `checktick-light` and `checktick-dark` are mapped to the actual preset names (e.g., `corporate` or `business`)
  - Custom CSS from the theme generator is injected as CSS variables under the `checktick-light` and `checktick-dark` theme selectors
  - Theme switching happens via JavaScript that maps the logical names to the actual presets
  - Environment variables `BRAND_THEME_PRESET_LIGHT` and `BRAND_THEME_PRESET_DARK` provide deployment-level defaults

1. Survey-level theming — per-survey customization

- Who: Survey owners/managers
- Applies to: Specific survey views (dashboard, detail, groups, and builder)
- What you can configure:
  - Optional title/icon override
  - Fonts (heading/body stacks and font CSS URL)
  - Theme CSS overrides for light/dark from the daisyUI builder (variables only)
- How it’s applied:
  - Survey templates include a `head_theme_overrides` block to inject per-survey font CSS and daisyUI variable overrides, and an `icon_link` block to set a per-survey favicon.
  - Per-survey overrides take precedence on those pages because they’re injected in-page.

### Precedence and merge behavior

- Base daisyUI presets (e.g., `nord`, `business`) provide the foundation
- Project-level custom CSS from Theme Generator refines the preset across the entire site
- Survey-level overrides win on survey pages where they're included
- Avoid mixing heavy global CSS with inline colors; prefer daisyUI variables so all layers compose cleanly

## How to configure project-level theming

1. Go to Profile → Project theme and brand (admin-only)

2. Choose theme presets:

   - Light theme preset: Select from 20 options (default: `corporate`)
   - Dark theme preset: Select from 12 options (default: `business`)
   - The logical names `checktick-light` and `checktick-dark` are preserved for compatibility

3. Set branding:

   - Icon: either upload an SVG/PNG or paste an absolute URL
   - Dark mode icon: optional separate icon for dark theme
   - Fonts: set heading/body stacks; optionally paste a Font CSS URL (e.g. Google Fonts)

4. Advanced: Custom Theme CSS (optional):

   - For power users: paste CSS variables from the [daisyUI Theme Generator](https://daisyui.com/theme-generator/)
   - Copy variables for both light and dark themes if you need precise control
   - Paste into "Light theme CSS" and "Dark theme CSS" fields
   - Custom CSS overrides the selected preset
   - We normalize builder variables into daisyUI runtime variables and inject them under the `checktick-light` and `checktick-dark` theme selectors

5. Save — the base template will now serve your icon, fonts, and theme colors sitewide

Tip: Most users should just select a preset. Custom CSS is only needed for unique branding requirements.

## How to configure survey-level theming

1. Open a survey → Dashboard → "Survey style"

2. Optional: set a Title override and Icon URL

3. Fonts: set heading/body stacks and optionally a Font CSS URL

4. Theme name: normally leave as-is unless you're switching between daisyUI themes

5. Primary color: provide a hex like `#ff3366`; the server will convert it to the appropriate color space / variables

6. If you have daisyUI builder variables for this survey's unique palette:

   - Paste the light/dark sets in their respective fields (where available)
   - The page will inject them under `[data-theme="checktick-light"]` and `[data-theme="checktick-dark"]`

These overrides only apply on survey pages and do not affect the rest of the site.

## Acceptable daisyUI builder CSS

**Note**: Most users should just select a theme preset in Profile settings. This section is for advanced customization only.

Paste only variable assignments from the [daisyUI Theme Generator](https://daisyui.com/theme-generator/), for example:

```txt
--color-primary: oklch(65% 0.21 25);
--radius-selector: 1rem;
--depth: 0;
```

We map these to daisyUI runtime variables (e.g., `--p`, `--b1`, etc.) and inject them under the `checktick-light` and `checktick-dark` theme selectors. Avoid pasting arbitrary CSS rules; stick to variables for predictable results.

## Troubleshooting

- Colors don't apply: Check for any hardcoded inline CSS overriding CSS variables. Prefer variables and themes.
- Wrong theme shown after changes: Your theme selection is cached in browser localStorage. Use the light/dark toggle in your profile or clear localStorage to reset.
- Preset not applying: Make sure you saved the profile settings and refreshed the browser. Check browser DevTools to see the `data-theme` attribute on `<html>`.
- Icon not showing: If you uploaded an icon, make sure media is configured. If using a URL, verify it's reachable. The app falls back to a default SVG if none is set.

## Typography and button links

`@tailwindcss/typography` styles content in `.prose`, including links. To avoid underlines and color overrides on daisyUI button anchors, the build loads Typography first and daisyUI second, with a small Typography override to skip underlines on `a.btn`.

- To opt a specific element out of Typography effects, add `not-prose`.

## Rendering forms with daisyUI

We ship a filter and partials to standardize Django form rendering.

### Template filter: `add_classes`

File: `checktick_app/surveys/templatetags/form_extras.py`

Usage:

```django
{% load form_extras %}
{{ form.field|add_classes:"input input-bordered w-full" }}
```

### Partial: `components/form_field.html`

File: `checktick_app/templates/components/form_field.html`

Context:

- `field` (required): bound Django form field
- `label` (optional)
- `help` (optional)
- `classes` (optional): override default classes

Defaults when `classes` isn’t provided:

- Text-like inputs: `input input-bordered w-full`
- Textarea: `textarea textarea-bordered w-full`
- Select: `select select-bordered w-full`

Example:

```django
{% include "components/form_field.html" with field=form.name label="Name" %}
{% include "components/form_field.html" with field=form.slug label="URL Name or 'Slug' (optional)" help="If left blank, a slug will be generated from the name." %}
{% include "components/form_field.html" with field=form.description label="Description" %}
```

### Render an entire form

Helper that iterates over visible fields:

```django
{% include "components/render_form_fields.html" with form=form %}
```

This uses `form_field` for each field. For radio/checkbox groups needing custom layout, render bespoke markup with daisyUI components or pass `classes` explicitly.

### Choice components

For grouped choices, use the specialized components:

- `components/radio_group.html` — radios with daisyUI
- `components/checkbox_group.html` — checkboxes with daisyUI

Examples:

```django
{% include "components/radio_group.html" with name="account_type" label="Account type" choices=(("simple","Simple user"),("org","Organisation")) selected='simple' inline=True %}
```

```django
{% include "components/checkbox_group.html" with name="interests" label="Interests" choices=(("a","A"),("b","B")) selected=("a",) %}
```

## Rebuild CSS

**Tailwind CSS v4 uses CSS-based configuration** instead of `tailwind.config.js`. Configuration is done via `@import` and `@plugin` directives in CSS files.

Whenever you change CSS files or add new templates:

```bash
npm run build:css
```

If running under Docker, rebuild the image or ensure your build step runs inside the container.

### Tailwind v4 architecture

- **CLI**: Uses `@tailwindcss/cli` package (separate from main `tailwindcss` package)
- **No config file**: Configuration moved to CSS using `@import`, `@plugin`, and `@theme` directives
- **daisyUI v5**: All 39 themes loaded via `@plugin "daisyui" { themes: all; }` in `daisyui_themes.css`

### Single stylesheet entry

- Unified Tailwind/daisyUI input: `checktick_app/static/css/daisyui_themes.css`
- Built output: `checktick_app/static/build/styles.css`
- Loaded globally in `checktick_app/templates/base.html` via `{% static 'build/styles.css' %}`

Do not add other `<link rel="stylesheet">` tags or separate CSS files; extend styling through Tailwind utilities, daisyUI components, or minimal additions inside the unified entry file.


## Breadcrumbs component

We ship a reusable DaisyUI-style breadcrumbs component with icons.

- File: `checktick_app/templates/components/breadcrumbs.html`
- Purpose: Provide consistent navigation crumbs across survey pages
- Icons:
  - Survey: clipboard icon
  - Question group: multiple documents icon
  - Question (current): single document icon

### How to use

There are two ways to render breadcrumbs, depending on what’s most convenient in your template.

1. Numbered crumb parameters (template-friendly)

Pass labeled crumbs in order. For any crumb you pass, you can optionally include an `*_href` to make it a link. The last crumb usually omits `*_href` to indicate the current page.

```django
{% include 'components/breadcrumbs.html' with
  crumb1_label="Survey Dashboard"
  crumb1_href="/surveys/"|add:survey.slug|add:"/dashboard/"
  crumb2_label="Question Group Builder"
  crumb2_href="/surveys/"|add:survey.slug|add:"/builder/"
  crumb3_label="Question Builder"
%}
```

1. Items iterable (tuple list)

If you already have a list, pass `items` as an iterable of `(label, href)` tuples. Use `None` for href on the current page.

```django
{% include 'components/breadcrumbs.html' with
  items=(("Survey Dashboard", "/surveys/"|add:survey.slug|add:"/dashboard/"),
         ("Question Group Builder", "/surveys/"|add:survey.slug|add:"/builder/"),
         ("Question Builder", None))
%}
```

### Styling

Breadcrumbs inherit DaisyUI theme colors and are further tuned globally so that:

- Links are lighter by default and only underline on hover
- The current (non-link) crumb is slightly lighter to indicate context

These tweaks live in the single CSS entry at `checktick_app/static/src/tailwind.css` in a small component layer block:

```css
@layer components {
  .breadcrumbs a {
    @apply no-underline text-base-content/70 hover:underline hover:text-base-content/90;
  }
  .breadcrumbs li > span {
    @apply text-base-content/60;
  }
  /* Ensure Typography (.prose) doesn’t re-add underlines */
  .prose :where(.breadcrumbs a):not(:where([class~="not-prose"])) {
    @apply no-underline text-base-content/70 hover:underline hover:text-base-content/90;
  }
}
```

Any updates here require a CSS rebuild.

### Page conventions

- Survey dashboard pages begin with a clipboard icon crumb (Survey)
- Survey-level builder links (groups) show multiple documents
- Group-level question builder shows a single document for the active page

Keep breadcrumb labels terse and consistent (e.g., “Survey Dashboard”, “Question Group Builder”, “Question Builder”).

## Internationalisation (i18n)

This project ships with Django i18n enabled. Themes and UI copy should use Django’s translation tags and helpers so labels, buttons, and help text can be translated cleanly without forking templates.

### Template basics

- Load i18n in templates that have translatable text:

```django
{% load i18n %}
```

- Translate short strings:

```django
{% trans "Manage groups" %}
```

- Translate sentences with variables using blocktrans:

```django
{% blocktrans %}Groups for {{ survey.name }}{% endblocktrans %}
```

- Prefer assigning translated values to variables when you need them inside attributes (e.g., placeholders) or component includes (breadcrumbs):

```django
{% trans "Surveys" as bc_surveys %}
{% include 'components/breadcrumbs.html' with crumb1_label=bc_surveys crumb1_href="/surveys/" %}

{% trans "Defaults to platform title" as ph_title %}
<input placeholder="{{ ph_title }}" />
```

- Plurals with blocktrans:

```django
{% blocktrans count q=group.q_count %}
{{ q }} question
{% plural %}
{{ q }} questions
{% endblocktrans %}
```

Notes

- Don’t wrap dynamic values (like `survey.name`) in `{% trans %}`; translate only the surrounding text.
- Keep punctuation and capitalization stable to help translators.
- For long help text, use `{% blocktrans %}` to keep the string intact for translators.

### Python code

Use Django’s translation utilities in Python code:

```python
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

msg = _("You don’t have permission to edit this survey.")

label = ngettext(
  "{count} response",  # singular
  "{count} responses", # plural
  total,
).format(count=total)
```

For lazily-evaluated strings in model fields or settings, prefer `gettext_lazy`:

```python
from django.utils.translation import gettext_lazy as _

class MyForm(forms.Form):
  name = forms.CharField(label=_("Name"))
```

### Message extraction and compilation (Docker + Poetry)

Run these inside the web container so they use the project environment. Replace `fr` with your target language code (ISO 639-1).

```bash
# Create/update .po files for templates and Python strings
docker compose exec web poetry run python manage.py makemessages -l fr

# Optionally, extract JavaScript strings (if using Django’s JS i18n)
docker compose exec web poetry run python manage.py makemessages -d djangojs -l fr

# After translating the .po files, compile to .mo
docker compose exec web poetry run python manage.py compilemessages
```

Defaults and structure

- Locale files can live per app (e.g., `checktick_app/surveys/locale/`) or at the project root `locale/`. Django will discover both.
- Ensure `USE_I18N = True` in settings (it is by default in this project).
- Ignore build and vendor dirs during extraction to avoid noise (Django’s `makemessages` respects `.gitignore` and you can add `-i` patterns if needed).

### Theming + i18n tips

- Translate UI labels, headings, and helper text; leave CSS variables and class names untouched.
- When using DaisyUI/Tailwind inside `.prose`, prefer wrapping button links with `.btn` so Typography doesn’t restyle them. Translations won’t affect classes.
- Breadcrumbs: translate labels via `{% trans %} … as var %}` before passing to the component.
- For placeholders/tooltips, assign translated strings to variables and reference them in attributes.

## Theme selection (System/Light/Dark)

End users can choose how the UI looks on the Profile page. The selector supports:

- System — follow the operating system’s preference (auto-switches if the OS changes)
- Light — force the custom light theme (`checktick-light`)
- Dark — force the custom dark theme (`checktick-dark`)

How it works:

- The active preference is saved to `localStorage` under the key `checktick-theme`.
- Accepted values: `system`, `checktick-light`, `checktick-dark`.
- On first visit, the server’s default (`data-theme` on `<html>`) is used; if it matches the system preference, the selector shows `System`.
- Changing the selector immediately updates `html[data-theme]` and persists the choice.
- When `System` is selected, the UI updates automatically on OS theme changes via `prefers-color-scheme`.

Relevant files:

- Profile UI: `checktick_app/core/templates/core/profile.html`
- Runtime logic: `checktick_app/static/js/theme-toggle.js`
- Script is loaded in: `checktick_app/templates/base.html`

## Branding and customization

This project supports organisation branding at the platform level with sensible accessibility defaults and light/dark variants.

### Navbar brand icon

- The navbar shows the brand icon next to the site title.
- Source priority (first available wins):
  1) Uploaded file on the Profile page (light: `icon_file`, dark: `icon_file_dark`)
  2) URL saved on the Profile page (light: `icon_url`, dark: `icon_url_dark`)
  3) Django settings (`BRAND_ICON_URL`, `BRAND_ICON_URL_DARK`)
  4) Inline SVG fallback (a neutral stroke-based mark)
- Dark mode: if a dark icon is set (uploaded or URL), it is shown automatically when the active theme contains `checktick-dark`.
- The icon includes `alt` and `title` attributes derived from `BRAND_ICON_ALT` and `BRAND_ICON_TITLE` (defaulting to the site title).
- Size can be customized with `BRAND_ICON_SIZE_CLASS` (Tailwind classes like `w-8 h-8`) or `BRAND_ICON_SIZE` (number -> `w-{n} h-{n}`). Defaults to `w-6 h-6`.

Accessibility:

- Icons are rendered with `alt`/`title` and, for inline SVG, `role="img"` and `aria-label` to ensure assistive technology support.
- Prefer high-contrast icons. If providing separate light/dark assets, test both on your themes.

### Fonts and CSS variables

- Heading/body font stacks are applied via CSS variables (`--font-heading` and `--font-body`).
- Optional `font_css_url` allows fast integration with Google Fonts or similar. Ensure stacks match the families you load.

### Survey-specific overrides

- Surveys can override icon, fonts, and DaisyUI variables on their pages. See “How to configure survey-level theming” above.

### Rebuild reminder

- Changes to Tailwind/DaisyUI configs or new templates require rebuilding the CSS bundle.
