# Branding and Theme Settings

This guide explains CheckTick's 3-tier theme system and how to customize the appearance at different levels. Whether you're a platform admin, organization owner, or survey creator, you can control the look and feel of your CheckTick instance.

## Overview: 3-Tier Theme Hierarchy

CheckTick uses a **cascading theme system** with three levels:



```- BRAND_TITLE (str) — Default site title. Example: "CheckTick"

┌─────────────────────────────────────┐- BRAND_ICON_URL (str) — URL or static path to the site icon shown in the navbar and as favicon if no uploaded icon.

│  1. Platform Theme                  │  ← Superuser sets (affects all users)- BRAND_ICON_URL_DARK (str) — Optional dark-mode icon URL. Shown when dark theme is active.

│     (Deployment default)            │- BRAND_ICON_ALT (str) — Alt text for the brand icon. Defaults to BRAND_TITLE.

└─────────────────────────────────────┘- BRAND_ICON_TITLE (str) — Title/tooltip for the brand icon. Defaults to BRAND_TITLE.

              ↓ Overrides- BRAND_ICON_SIZE_CLASS (str) — Tailwind size classes for the icon. Example: "w-8 h-8".

┌─────────────────────────────────────┐- BRAND_ICON_SIZE (int or str) — Numeric size that maps to `w-{n} h-{n}`. Example: 6, 8. Ignored if BRAND_ICON_SIZE_CLASS is set.

│  2. Organization Theme              │  ← Org owner sets (affects org members)

│     (Per-organization)              │## Theme settings (environment variables)

└─────────────────────────────────────┘

              ↓ Overrides- BRAND_THEME (str) — Default logical theme name. Values: "checktick-light" or "checktick-dark". Default: "checktick-light".

┌─────────────────────────────────────┐- BRAND_THEME_PRESET_LIGHT (str) — daisyUI preset for light mode. Default: "nord". Available: light, cupcake, bumblebee, emerald, corporate, retro, cyberpunk, valentine, garden, lofi, pastel, fantasy, nord, cmyk, autumn, acid, lemonade, winter, nord, sunset.

│  3. Survey Theme                    │  ← Survey creator sets (affects survey pages)- BRAND_THEME_PRESET_DARK (str) — daisyUI preset for dark mode. Default: "business". Available: dark, synthwave, halloween, forest, aqua, black, luxury, dracula, business, night, coffee, dim.

│     (Per-survey)                    │- BRAND_FONT_HEADING (str) — CSS font stack for headings.

└─────────────────────────────────────┘- BRAND_FONT_BODY (str) — CSS font stack for body.

```- BRAND_FONT_CSS_URL (str) — Optional font CSS href (e.g., Google Fonts).

- BRAND_THEME_CSS_LIGHT (str) — Custom DaisyUI variable overrides for light theme (advanced).

**How it works:**- BRAND_THEME_CSS_DARK (str) — Custom DaisyUI variable overrides for dark theme (advanced).



- Each level can override the level above it## Organization-level theming (SiteBranding model)

- Changes at one level don't affect other levels

- Users see the theme from the most specific level that applies to themOrganization admins can override environment defaults via the Profile page. Settings are stored in the `SiteBranding` database model:



## Permissions- **default_theme** — Logical theme name (checktick-light or checktick-dark)

- **theme_preset_light** — daisyUI preset for light mode (20 options)

Different users can control different levels:- **theme_preset_dark** — daisyUI preset for dark mode (12 options)

- **icon_file** / **icon_url** — Light mode icon (uploaded file takes precedence over URL)

| Level | Who Can Configure | Where | Affects |- **icon_file_dark** / **icon_url_dark** — Dark mode icon

|-------|------------------|-------|---------|- **font_heading** / **font_body** / **font_css_url** — Font configuration

| **Platform** | Superusers only | Django Admin or environment variables | All users (default) |- **theme_light_css** / **theme_dark_css** — Custom CSS from daisyUI Theme Generator (optional, overrides presets)

| **Organization** | Organization owners | Profile page | All organization members |

| **Survey** | Survey creators | Survey dashboard | Survey pages only |**Precedence**: Database values → Environment variables → Built-in defaults



## 1. Platform-Level Themes (Superusers)## How theming works



Platform administrators set the default theme for the entire CheckTick deployment.1. **Logical theme names** (checktick-light, checktick-dark) are used for:

   - User preference storage (localStorage)

### Who Can Configure   - Theme toggle UI

   - Database field values

- **Superusers only** - Users with Django admin access

- Regular users and organization owners cannot change platform defaults2. **Actual daisyUI preset names** (nord, business, etc.) are applied to the DOM:

   - `<html data-theme="nord">` for light mode

### Where to Configure   - `<html data-theme="business">` for dark mode

   - JavaScript maps logical names to presets based on SiteBranding settings

**Django Admin** (recommended for runtime changes):

3. **Custom CSS overrides** from daisyUI Theme Generator can override preset colors while keeping the base theme structure.

1. Log in as superuser

2. Navigate to `/admin/`## Survey style fields (per-survey)

3. Click "Site Branding" under Core

4. Edit theme presets, icons, fonts, custom CSS- title — Optional page title override

- icon_url — Optional per-survey favicon/icon

**Environment Variables** (recommended for deployment):- theme_name — DaisyUI theme name for the survey pages

- primary_color — Hex color (e.g., #ff3366); normalized to the correct color variables

- See [Self-Hosting: Platform Theme Configuration](self-hosting-themes.md)- font_heading — CSS font stack

- Set `BRAND_THEME_PRESET_LIGHT`, `BRAND_THEME_PRESET_DARK`, etc.- font_body — CSS font stack

- font_css_url — Optional font CSS href

### What You Can Configure- theme_css_light — Light theme DaisyUI variable overrides (from builder)

- theme_css_dark — Dark theme DaisyUI variable overrides (from builder)

- **Theme presets** - Choose from 20 light themes and 12 dark themes

- **Site icons** - Upload or provide URLs for light/dark mode icons## Where to look in the code

- **Fonts** - Set heading and body font stacks, external font CSS

- **Custom CSS** (advanced) - Paste variables from daisyUI Theme Generator- **Tailwind v4 entry point**: `checktick_app/static/css/daisyui_themes.css` (CSS-based config, no JS config file)

- **Theme utility**: `checktick_app/core/themes.py` (preset lists, parsing functions)

### Available Theme Presets- **Base templates**: `checktick_app/templates/base.html`, `base_minimal.html`, `admin/base_site.html`

- **Branding context**: `checktick_app/context_processors.py` (builds the `brand` object)

**20 Light Themes:**- **Profile UI**: `checktick_app/core/templates/core/profile.html` (theme preset dropdowns)

nord (default), nord, light, cupcake, bumblebee, emerald, corporate, retro, cyberpunk, valentine, garden, lofi, pastel, fantasy, cmyk, autumn, acid, lemonade, winter, sunset- **Theme switcher JS**: `checktick_app/static/js/theme-toggle.js`, `admin-theme.js`

- **Survey dashboard style form**: `checktick_app/surveys/templates/surveys/dashboard.html`

**12 Dark Themes:**

business (default), dark, synthwave, halloween, forest, aqua, black, luxury, dracula, night, coffee, dim## Rebuilding the CSS



## 2. Organization-Level Themes (Organization Owners)Tailwind CSS v4 uses the `@tailwindcss/cli` package:



Organization owners can customize their organization's appearance, overriding platform defaults for all members.```bash

npm run build:css

### Who Can Configure```



- **Organization owners only** - The user who created the organizationOr in Docker:

- Organization members and survey creators cannot change organization themes

```bash

### Where to Configuredocker compose exec web npm run build:css

```

1. Log in as organization owner

2. Navigate to `/profile`The build process:

3. Scroll to "Organization Theme" section

4. Click "Edit Theme" button- Input: `checktick_app/static/css/daisyui_themes.css`

- Output: `checktick_app/static/build/styles.css` (minified)

### What You Can Configure- Build time: ~250ms

- All 39 daisyUI themes included (192KB minified)

**Basic Settings:**

- Light theme preset (choose from 20 options)
- Dark theme preset (choose from 12 options)

**Advanced Settings** (optional):

- Custom CSS for light theme
- Custom CSS for dark theme

### How to Select a Theme Preset

1. Click "Edit Theme" in your profile
2. Choose a light theme from the first dropdown
3. Choose a dark theme from the second dropdown
4. Click "Save"

**Example:** Select "corporate" for light mode and "luxury" for dark mode to give your organization a professional look.

### How to Reset to Platform Defaults

If you want your organization to use the platform's default theme again:

1. Navigate to `/profile`
2. Scroll to "Organization Theme" section
3. Click "Reset to Defaults" button
4. Confirm

This clears all custom organization theme settings and falls back to the platform theme.

### Viewing Current Theme

The profile page shows your current theme status:

- **"Platform Default"** - Using the deployment's default theme
- **Theme name** (e.g., "corporate") - Using a custom organization theme

## 3. Survey-Level Themes (Survey Creators)

Survey creators can customize individual surveys with unique branding and colors.

### Who Can Configure

- **Survey owners** - The user who created the survey
- **Survey creators** - Users with creator role on the survey
- Organization admins cannot override survey themes (surveys retain autonomy)

### Where to Configure

1. Open your survey
2. Click "Dashboard" tab
3. Scroll to "Survey Style" section
4. Edit theme settings
5. Save changes

### What You Can Configure

- **Title override** - Custom page title for survey pages
- **Icon URL** - Custom icon/favicon for survey
- **Theme name** - daisyUI theme preset
- **Primary color** - Hex color code (e.g., `#ff3366`)
- **Fonts** - Heading/body font stacks, external font CSS
- **Custom CSS** (advanced) - Light/dark theme variables

### When to Use Survey Themes

Survey-level themes are useful when:

- Running multiple surveys with different branding
- Creating survey-specific color schemes
- Testing new themes without affecting other surveys
- White-labeling surveys for different clients/departments

## Using the daisyUI Theme Generator

For advanced customization beyond preset themes, use the daisyUI Theme Generator to create custom color schemes.

### When to Use Custom CSS

**Use custom CSS when:**

- Your organization has specific brand colors
- Preset themes don't match your color scheme
- You need precise control over colors, borders, shadows

**Use preset themes when:**

- You're happy with one of the 32 built-in themes
- You want quick, professional results
- You don't have specific brand color requirements

### How to Generate Custom Theme CSS

1. **Visit the Theme Generator:**
   - Go to [daisyui.com/theme-generator](https://daisyui.com/theme-generator/)

2. **Choose a base preset:**
   - Start with a preset that's close to your desired look
   - This provides a good foundation

3. **Customize colors:**
   - Adjust primary, secondary, accent colors
   - Modify background, text colors
   - Set border radius, shadows

4. **Copy the CSS variables:**
   - Click "Copy CSS" button
   - The generated code contains CSS variable declarations

5. **Paste into CheckTick:**
   - For organizations: Paste into "Advanced: Custom CSS" fields in profile
   - For surveys: Paste into survey style form
   - Paste light theme variables in "Light theme CSS"
   - Paste dark theme variables in "Dark theme CSS"

### What to Paste

✅ **DO paste:**

```css
--color-primary: oklch(65% 0.21 25);
--color-secondary: oklch(70% 0.15 200);
--radius-selector: 1rem;
```

❌ **DON'T paste:**

```css
:root {
  --color-primary: oklch(65% 0.21 25);
}
```

**Important:** Paste only the variable declarations, not the `:root` or `[data-theme="..."]` selectors. CheckTick automatically adds the proper selectors.

## Theme Selection (Light/Dark/System)

End users can choose how CheckTick appears on their device:

### User Preference Options

1. **System** - Follow operating system theme (auto-switches)
2. **Light** - Always use light mode theme
3. **Dark** - Always use dark mode theme

### How Users Change Theme

1. Log in to CheckTick
2. Navigate to `/profile`
3. Find "Theme Selection" section
4. Choose "System", "Light", or "Dark"
5. Theme changes immediately

### How It Works

- User preference stored in browser localStorage
- JavaScript applies the correct theme on page load
- When "System" is selected, theme updates automatically when OS theme changes
- Light/Dark choice overrides system preference

## Understanding Theme Precedence

When multiple theme levels are configured, CheckTick uses this precedence:

### Precedence Order (Highest to Lowest)

1. **Survey theme** - Applies only on survey pages
2. **Organization theme** - Applies to all org members (except on survey pages with custom themes)
3. **Platform theme** - Default for all users

### Example Scenarios

**Scenario 1: Platform + Organization**

- Platform set to: nord (light), business (dark)
- Organization set to: corporate (light), luxury (dark)
- **Result:** Organization members see corporate/luxury, non-members see nord/business

**Scenario 2: All Three Levels**

- Platform: nord/business
- Organization: corporate/luxury
- Survey: cupcake/forest
- **Result:** Survey pages show cupcake/forest, other pages show corporate/luxury

**Scenario 3: Organization Reset**

- Organization previously had custom theme
- Owner clicks "Reset to Defaults"
- **Result:** Organization members now see platform theme (nord/business)

## Troubleshooting

### Theme Not Applying

**Problem:** Changed theme but still seeing old theme

**Solutions:**

1. Hard refresh browser (`Ctrl+Shift+R` or `Cmd+Shift+R`)
2. Clear browser localStorage: `localStorage.removeItem('checktick-theme')`
3. Check that you have permission to change that theme level
4. Verify you saved the changes

### Colors Look Wrong

**Problem:** Custom colors not showing correctly

**Solutions:**

1. Verify you pasted only CSS variables (no selectors)
2. Ensure OKLCH color format is correct
3. Test colors in daisyUI Theme Generator first
4. Check both light and dark theme CSS

### Permission Denied

**Problem:** Can't access theme settings

**Check your role:**

- Platform themes: Must be superuser
- Organization themes: Must be organization owner
- Survey themes: Must be survey owner/creator

### Icons Not Showing

**Problem:** Custom icon not appearing

**Solutions:**

1. For uploaded files: Ensure file is SVG, PNG, JPG, or WebP
2. For URLs: Verify URL is absolute and accessible
3. Check file size is within limits
4. Verify media files are served correctly

### Theme Doesn't Persist

**Problem:** Theme resets when changing pages

**Solution:** This is likely a browser localStorage issue. Check:

1. Browser allows localStorage (not in incognito/private mode)
2. No browser extensions blocking storage
3. Cookie/storage settings allow site data

## Best Practices

### For Platform Administrators

- Set sensible defaults that work for most users
- Choose accessible themes with good contrast
- Test both light and dark modes
- Document any custom CSS for future reference

### For Organization Owners

- Consider your organization's brand colors
- Test themes with actual users before rolling out
- Keep accessibility in mind (contrast ratios)
- Use "Reset to Defaults" if unsure about changes

### For Survey Creators

- Only customize surveys that truly need unique branding
- Stick to presets unless you have specific requirements
- Test survey themes on different devices
- Ensure colors work for both light and dark modes

### Accessibility Considerations

- Maintain sufficient color contrast (WCAG AA minimum: 4.5:1)
- Test themes with screen readers
- Don't rely on color alone to convey information
- Consider colorblind users when choosing colors

## Related Documentation

- [Self-Hosting: Platform Theme Configuration](self-hosting-themes.md) - Deployment and environment variable configuration
- [Themes (Developer Guide)](themes.md) - Technical implementation details
- [User Management](user-management.md) - Understanding user roles and permissions

## Getting Help

If you encounter issues with theming:

1. Check this guide first
2. Review [Getting Help](getting-help.md) for support options
3. Search existing GitHub discussions
4. Create a new discussion with:
   - Your role (superuser/org owner/survey creator)
   - What you're trying to achieve
   - Steps you've already tried
   - Screenshots if applicable
