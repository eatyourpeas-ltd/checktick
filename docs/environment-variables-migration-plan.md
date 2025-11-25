# Environment Variables Migration Plan

## Overview

This document defines which configuration options should remain as environment variables and which should be migrated to UI-based management via Django management commands and admin interface.

**Guiding Principles:**
1. **Infrastructure & Security** → Environment Variables (`.env` file)
2. **Branding & Customization** → Management Commands + UI (Django admin/custom views)
3. **Operational Settings** → Keep flexible (can be env vars with UI overrides)

## Current Theme System Architecture

CheckTick uses a **3-tier theme cascade** with the following precedence (highest to lowest):

1. **Survey-level themes** (`Survey.style` JSON field) - Overrides all
2. **Organization-level themes** (`Organization` theme fields) - Overrides platform defaults
3. **Platform-level themes** (`SiteBranding` model + ENV fallbacks) - Base defaults

### Implementation Details

**Platform Level** (what we're migrating):

- Currently: ENV variables (`BRAND_*`) → `settings.py` → `context_processors.py`
- After migration: `SiteBranding` model (DB) → `context_processors.py` → templates
- ENV variables become **fallbacks only** if `SiteBranding` not configured

**Organization Level** (already implemented):

- `Organization` model has theme fields: `default_theme`, `theme_preset_light`, `theme_preset_dark`, `theme_light_css`, `theme_dark_css`
- Applied in `context_processors.py` if user is organization member
- Overrides platform defaults

**Survey Level** (already implemented):

- `Survey.style` JSON field contains theme overrides
- Applied per-survey in views/templates
- Highest priority - overrides both platform and organization themes

### Theme CSS Generation

The system uses `generate_theme_css_for_brand()` function (in `checktick_app/core/themes.py`) to:

1. Take DaisyUI preset names (e.g., "nord", "business")
2. Generate CSS variables for runtime theme switching
3. Allow custom CSS overrides from DaisyUI Theme Generator

This works at all three levels (platform, organization, survey).

---

## Category 1: KEEP as Environment Variables

These settings are infrastructure-level, security-sensitive, or need to be set before the application starts. They should **remain in `.env` files**.

### Core Infrastructure

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `DEBUG` | Enable debug mode | Security - must be False in production |
| `SECRET_KEY` | Django secret key | Security - required at startup |
| `ALLOWED_HOSTS` | Allowed domain names | Security - required at startup |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins for CSRF | Security - required at startup |
| `SECURE_SSL_REDIRECT` | Force HTTPS redirects | Security - required at startup |
| `SITE_URL` | Base URL for emails | Infrastructure - needed for emails |

### Database Configuration

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `DATABASE_URL` | Database connection string | Infrastructure - required at startup |
| `POSTGRES_DB` | PostgreSQL database name | Infrastructure - for included container |
| `POSTGRES_USER` | PostgreSQL username | Infrastructure - for included container |
| `POSTGRES_PASSWORD` | PostgreSQL password | Security - credential management |

### Email Provider (SMTP)

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `DEFAULT_FROM_EMAIL` | From address for emails | Infrastructure - needed at startup |
| `SERVER_EMAIL` | Error report email | Infrastructure - needed at startup |
| `EMAIL_HOST` | SMTP server hostname | Infrastructure - connection required |
| `EMAIL_PORT` | SMTP server port | Infrastructure - connection required |
| `EMAIL_USE_TLS` | Use TLS encryption | Infrastructure - connection required |
| `EMAIL_USE_SSL` | Use SSL encryption | Infrastructure - connection required |
| `EMAIL_HOST_USER` | SMTP username | Security - credential management |
| `EMAIL_HOST_PASSWORD` | SMTP password | Security - credential management |
| `EMAIL_TIMEOUT` | SMTP timeout | Infrastructure - performance tuning |

**Rationale**: Email provider settings require credentials and are infrastructure-level configuration. These should remain in environment variables for security and deployment flexibility.

### Authentication (SSO/OIDC)

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `OIDC_RP_CLIENT_ID_GOOGLE` | Google OAuth client ID | Security - credential management |
| `OIDC_RP_CLIENT_SECRET_GOOGLE` | Google OAuth secret | Security - credential management |
| `OIDC_RP_CLIENT_ID_AZURE` | Azure AD client ID | Security - credential management |
| `OIDC_RP_CLIENT_SECRET_AZURE` | Azure AD secret | Security - credential management |
| `OIDC_OP_TENANT_ID_AZURE` | Azure AD tenant ID | Security - credential management |
| `OIDC_OP_JWKS_ENDPOINT_GOOGLE` | Google JWKS endpoint | Infrastructure - required at startup |
| `OIDC_OP_JWKS_ENDPOINT_AZURE` | Azure JWKS endpoint | Infrastructure - required at startup |

**Rationale**: OAuth/OIDC credentials are security-sensitive and must be available at application startup. These belong in environment variables or secret management systems.

### Spam Protection

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `HCAPTCHA_SITEKEY` | hCaptcha site key | Infrastructure - public key for forms |
| `HCAPTCHA_SECRET` | hCaptcha secret key | Security - credential management |

**Rationale**: Third-party service credentials should be in environment variables for security.

### External APIs

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `EXTERNAL_DATASET_API_URL` | RCPCH API endpoint | Infrastructure - required at startup |
| `EXTERNAL_DATASET_API_KEY` | RCPCH API key | Security - credential management |
| `LLM_URL` | LLM API endpoint | Infrastructure - service connection |
| `LLM_API_KEY` | LLM API key | Security - credential management |
| `LLM_AUTH_TYPE` | LLM auth method | Infrastructure - connection config |

**Rationale**: External API credentials and endpoints are infrastructure configuration that should remain in environment variables.

### Account Tier System (NEW)

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `SELF_HOSTED` | Enable self-hosted mode | Infrastructure - changes tier behavior |
| `PAYMENT_PROVIDER` | Payment provider name | Infrastructure - integration required |
| `PAYMENT_API_KEY` | Payment provider key | Security - credential management |
| `PAYMENT_WEBHOOK_SECRET` | Payment webhook secret | Security - credential management |

**Rationale**: These control fundamental application behavior and payment integrations, requiring environment-level configuration.

### Data Governance (Optional)

| Variable | Purpose | Why ENV? |
|----------|---------|----------|
| `CHECKTICK_DEFAULT_RETENTION_MONTHS` | Default retention period | Policy - organizational default |
| `CHECKTICK_MAX_RETENTION_MONTHS` | Maximum retention allowed | Policy - compliance constraint |
| `CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS` | Export link expiry | Policy - security setting |
| `CHECKTICK_WARN_BEFORE_DELETION_DAYS` | Warning schedule | Policy - notification timing |

**Rationale**: These are policy-level settings that typically don't change frequently. Can remain as environment variables with sensible defaults. Could optionally be moved to UI in future if needed.

---

## Category 2: MIGRATE to Management Commands + UI

These settings are customization-focused and benefit from UI-based management. They should be **removed from environment variables** and managed via Django admin or custom views.

### Branding & Theming

| Current Variable | New Management Method | UI Location |
|------------------|----------------------|-------------|
| `BRAND_TITLE` | ❌ Remove from ENV | Django Admin → SiteBranding |
| `BRAND_ICON_URL` | ❌ Remove from ENV | Django Admin → SiteBranding (icon_url field) |
| `BRAND_ICON_URL_DARK` | ❌ Remove from ENV | Django Admin → SiteBranding (icon_url_dark field) |
| `BRAND_ICON_ALT` | ❌ Remove from ENV | Django Admin → SiteBranding (new field) |
| `BRAND_ICON_TITLE` | ❌ Remove from ENV | Django Admin → SiteBranding (new field) |
| `BRAND_ICON_SIZE_CLASS` | ❌ Remove from ENV | Django Admin → SiteBranding (new field) |
| `BRAND_ICON_SIZE` | ❌ Remove from ENV | Django Admin → SiteBranding (new field) |
| `BRAND_THEME` | ❌ Remove from ENV | Django Admin → SiteBranding (default_theme field) |
| `BRAND_THEME_PRESET_LIGHT` | ❌ Remove from ENV | Django Admin → SiteBranding (theme_preset_light field) |
| `BRAND_THEME_PRESET_DARK` | ❌ Remove from ENV | Django Admin → SiteBranding (theme_preset_dark field) |
| `BRAND_FONT_HEADING` | ❌ Remove from ENV | Django Admin → SiteBranding (font_heading field) |
| `BRAND_FONT_BODY` | ❌ Remove from ENV | Django Admin → SiteBranding (font_body field) |
| `BRAND_FONT_CSS_URL` | ❌ Remove from ENV | Django Admin → SiteBranding (font_css_url field) |
| `BRAND_THEME_CSS_LIGHT` | ❌ Remove from ENV | Django Admin → SiteBranding (theme_light_css field) |
| `BRAND_THEME_CSS_DARK` | ❌ Remove from ENV | Django Admin → SiteBranding (theme_dark_css field) |

**Management Command**:
```bash
# CLI configuration for initial setup or automation
python manage.py configure_branding \
  --theme-light=nord \
  --theme-dark=business \
  --logo=path/to/logo.png \
  --logo-dark=path/to/logo-dark.png
```

**UI Access**:
- **Self-hosted**: Superusers access via `/admin/core/sitebranding/` or custom view at `/branding/`
- **Hosted SaaS**: Enterprise tier users access custom branding view at `/branding/`

**Benefits of UI Management**:
1. ✅ No container restarts required for theme changes
2. ✅ File upload support for logos (better UX than mounting volumes)
3. ✅ Live preview of changes
4. ✅ Validation and error feedback
5. ✅ Version control via Django migrations for schema changes
6. ✅ Backup and restore via database dumps

---

## Category 3: HYBRID (ENV with UI Override)

Some settings may benefit from having both environment variable defaults AND UI override capability.

### Example: Site Title

```python
# In settings.py - use ENV var as default
SITE_TITLE = os.environ.get('SITE_TITLE', 'CheckTick')

# In template/view - check SiteBranding model first
branding = SiteBranding.objects.first()
site_title = branding.site_title if branding and branding.site_title else settings.SITE_TITLE
```

This allows:
- Quick setup via ENV var for basic deployments
- UI customization for advanced users who want live changes
- Fallback to ENV var if database not available

**Recommendation**: Start with pure UI management (Category 2). Add ENV fallbacks only if users request it for specific use cases.

---

## Implementation Plan

### Phase 1: Update SiteBranding Model ✅

The `SiteBranding` model already exists with most fields. Additions needed:

```python
class SiteBranding(models.Model):
    # Existing fields (already implemented)
    default_theme = models.CharField(...)
    icon_url = models.URLField(...)
    icon_file = models.FileField(...)
    icon_url_dark = models.URLField(...)
    icon_file_dark = models.FileField(...)
    font_heading = models.CharField(...)
    font_body = models.CharField(...)
    font_css_url = models.URLField(...)
    theme_preset_light = models.CharField(...)
    theme_preset_dark = models.CharField(...)
    theme_light_css = models.TextField(...)
    theme_dark_css = models.TextField(...)

    # NEW fields to add:
    site_title = models.CharField(max_length=255, default='CheckTick', blank=True)
    icon_alt = models.CharField(max_length=255, default='CheckTick', blank=True)
    icon_title = models.CharField(max_length=255, default='CheckTick', blank=True)
    icon_size_class = models.CharField(max_length=50, default='w-6 h-6', blank=True)
```

### Phase 2: Create Management Command ✅

**File**: `checktick_app/core/management/commands/configure_branding.py`

Already designed in `docs/account-tiers-implementation.md`. Supports:
- `--theme-light`, `--theme-dark`
- `--logo`, `--logo-dark`
- `--default-theme`
- Additional flags for other fields as needed

### Phase 3: Create/Enhance Branding UI ✅

**Option A**: Django Admin (simpler, faster to implement)
- Register `SiteBranding` model in admin
- Use existing admin interface
- Good for self-hosted superusers

**Option B**: Custom View (better UX, more control)
- Create custom view at `/branding/`
- File upload with preview
- Theme selector with live preview
- Better for Enterprise tier users

**Recommendation**: Start with Option A (admin), add Option B in future release if needed.

### Phase 4: Update Context Processors

Update `checktick_app/core/context_processors.py` to use `SiteBranding` model instead of environment variables:

```python
def branding(request):
    """Inject branding settings into all templates."""
    from .models import SiteBranding

    branding, _ = SiteBranding.objects.get_or_create(pk=1)

    return {
        'site_title': branding.site_title or 'CheckTick',
        'brand_icon_url': branding.icon_url,
        'brand_icon_file': branding.icon_file,
        # ... etc
    }
```

### Phase 5: Update Documentation

Update all self-hosting documentation to:
1. Remove branding environment variables from examples
2. Add instructions for using `python manage.py configure_branding`
3. Add instructions for accessing Django admin branding configuration
4. Update quickstart guide to focus on essential ENV vars only

**Files to Update**:
- ✅ `docs/self-hosting-quickstart.md`
- ✅ `docs/self-hosting-configuration.md`
- ✅ `docs/self-hosting-themes.md`
- ✅ `.env.example`
- ✅ `.env.selfhost`

### Phase 6: Migration Strategy

For existing deployments currently using ENV vars:

1. **Create migration** to populate `SiteBranding` from ENV vars on first run
2. **Deprecation warning** in startup logs if branding ENV vars are detected
3. **Gradual removal** - support ENV vars for 2 releases, then remove

**Example migration**:

```python
def migrate_env_to_db(apps, schema_editor):
    """One-time migration of environment variables to SiteBranding model."""
    import os
    SiteBranding = apps.get_model('core', 'SiteBranding')

    branding, created = SiteBranding.objects.get_or_create(pk=1)

    # Only update if fields are empty (don't override existing DB values)
    if not branding.site_title and os.environ.get('BRAND_TITLE'):
        branding.site_title = os.environ.get('BRAND_TITLE')

    if not branding.theme_preset_light and os.environ.get('BRAND_THEME_PRESET_LIGHT'):
        branding.theme_preset_light = os.environ.get('BRAND_THEME_PRESET_LIGHT')

    # ... etc for all fields

    branding.save()
```

---

## Updated `.env` Template

### Minimal Self-Hosting `.env`

```bash
# ===================================================================
# CheckTick Self-Hosting Configuration
# ===================================================================

# ========================
# REQUIRED: Security
# ========================
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,localhost
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
SECURE_SSL_REDIRECT=True
SITE_URL=https://yourdomain.com

# ========================
# REQUIRED: Database
# ========================
# Option 1: Use included PostgreSQL (default)
POSTGRES_DB=checktick
POSTGRES_USER=checktick
POSTGRES_PASSWORD=change-this-secure-password

# Option 2: External database (uncomment and use docker-compose.external-db.yml)
# DATABASE_URL=postgresql://user:pass@host:5432/checktick

# ========================
# REQUIRED: Email Provider
# ========================
DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
SERVER_EMAIL=server@yourdomain.com

# Choose ONE email provider:
# Gmail (for testing)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=youremail@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password

# OR Mailgun (recommended for production)
# EMAIL_HOST=smtp.eu.mailgun.org
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=postmaster@mg.yourdomain.com
# EMAIL_HOST_PASSWORD=your-mailgun-smtp-password

EMAIL_TIMEOUT=10

# ========================
# REQUIRED: External Datasets
# ========================
EXTERNAL_DATASET_API_URL=https://api.rcpch.ac.uk
EXTERNAL_DATASET_API_KEY=your-rcpch-api-key-here

# ========================
# OPTIONAL: Account Tiers
# ========================
# Set to true for self-hosted deployments (gives everyone Enterprise features)
SELF_HOSTED=true

# For hosted SaaS only:
# PAYMENT_PROVIDER=ryft
# PAYMENT_API_KEY=your-payment-api-key
# PAYMENT_WEBHOOK_SECRET=your-webhook-secret

# ========================
# OPTIONAL: Authentication
# ========================
# Google OAuth
# OIDC_RP_CLIENT_ID_GOOGLE=your-google-client-id
# OIDC_RP_CLIENT_SECRET_GOOGLE=your-google-client-secret

# Microsoft 365 / Azure AD
# OIDC_RP_CLIENT_ID_AZURE=your-azure-client-id
# OIDC_RP_CLIENT_SECRET_AZURE=your-azure-client-secret
# OIDC_OP_TENANT_ID_AZURE=your-tenant-id

# ========================
# OPTIONAL: Spam Protection
# ========================
# HCAPTCHA_SITEKEY=your-site-key
# HCAPTCHA_SECRET=your-secret-key

# ========================
# OPTIONAL: AI Features
# ========================
# LLM_URL=https://api.openai.com/v1/chat/completions
# LLM_API_KEY=your-api-key-here
# LLM_AUTH_TYPE=bearer

# ========================
# OPTIONAL: Data Governance
# ========================
# CHECKTICK_DEFAULT_RETENTION_MONTHS=6
# CHECKTICK_MAX_RETENTION_MONTHS=24
# CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS=7
# CHECKTICK_WARN_BEFORE_DELETION_DAYS=30,7,1

# ===================================================================
# BRANDING & THEMES: Now configured via Django admin or CLI
# Use: python manage.py configure_branding
# Or:  Django Admin → Core → Site Branding
# ===================================================================
```

**Size reduction**: ~40 lines removed (all BRAND_* variables)

---

## Scheduled Tasks Configuration

Scheduled tasks (cron jobs) should **remain as documented** - these are operational requirements, not configuration:

### Required Cron Jobs

```bash
# Data governance (REQUIRED for GDPR compliance)
0 2 * * * docker compose exec -T web python manage.py process_data_governance

# Survey progress cleanup (Recommended)
0 3 * * * docker compose exec -T web python manage.py cleanup_survey_progress

# External datasets sync (Recommended)
0 4 * * * docker compose exec -T web python manage.py sync_external_datasets

# NHS Data Dictionary sync (Recommended - weekly)
0 5 * * 0 docker compose exec -T web python manage.py sync_nhs_dd_datasets

# Question group templates sync (Optional)
0 6 * * * docker compose exec -T web python manage.py sync_global_question_group_templates
```

**No changes needed** - these remain as scheduled tasks in cron/systemd/Kubernetes CronJob.

---

## Summary

### Environment Variables: 37 variables
- **Security**: 6 (SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SECURE_SSL_REDIRECT, SITE_URL)
- **Database**: 4 (DATABASE_URL, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
- **Email**: 9 (DEFAULT_FROM_EMAIL, SERVER_EMAIL, EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_USE_SSL, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_TIMEOUT)
- **Authentication**: 7 (OIDC_RP_CLIENT_ID_GOOGLE, OIDC_RP_CLIENT_SECRET_GOOGLE, OIDC_RP_CLIENT_ID_AZURE, OIDC_RP_CLIENT_SECRET_AZURE, OIDC_OP_TENANT_ID_AZURE, OIDC_OP_JWKS_ENDPOINT_GOOGLE, OIDC_OP_JWKS_ENDPOINT_AZURE)
- **Spam Protection**: 2 (HCAPTCHA_SITEKEY, HCAPTCHA_SECRET)
- **External APIs**: 5 (EXTERNAL_DATASET_API_URL, EXTERNAL_DATASET_API_KEY, LLM_URL, LLM_API_KEY, LLM_AUTH_TYPE)
- **Account Tiers**: 4 (SELF_HOSTED, PAYMENT_PROVIDER, PAYMENT_API_KEY, PAYMENT_WEBHOOK_SECRET)
- **Data Governance**: 4 (CHECKTICK_DEFAULT_RETENTION_MONTHS, CHECKTICK_MAX_RETENTION_MONTHS, CHECKTICK_DOWNLOAD_LINK_EXPIRY_DAYS, CHECKTICK_WARN_BEFORE_DELETION_DAYS) - Optional

### Migrated to UI: 15 variables
- All `BRAND_*` variables (15 total)
- Managed via Django admin or `python manage.py configure_branding`

### Benefits of This Approach

✅ **Cleaner `.env` files** - Focus on essential infrastructure config
✅ **Better UX** - Self-hosters can customize branding without editing files
✅ **No restarts needed** - Theme changes apply immediately
✅ **File uploads** - Upload logos directly via UI instead of mounting volumes
✅ **Security** - Credentials stay in ENV vars where they belong
✅ **Flexibility** - Self-hosted and SaaS use same codebase
✅ **Enterprise features** - White-labeling via UI for Enterprise tier
✅ **Version control** - Theme schema changes via Django migrations

### Next Steps

1. ✅ Review this document and approve approach
2. ⏳ Add new fields to `SiteBranding` model
3. ⏳ Create migration to add new fields
4. ⏳ Update context processors to use model instead of ENV vars
5. ⏳ Update templates to use new context variables
6. ⏳ Create `configure_branding` management command
7. ⏳ Update Django admin for `SiteBranding`
8. ⏳ Update documentation (all self-hosting docs)
9. ⏳ Update `.env.example` and `.env.selfhost` templates
10. ⏳ Test migration path for existing deployments
