---
title: CDN Libraries
category: security
priority: 10
---

CheckTick self-hosts critical JavaScript libraries with Subresource Integrity (SRI) verification for enhanced security. This document describes the libraries, their purposes, and how to update them.

## Why Self-Host?

1. **Security**: SRI hashes verify file integrity, preventing CDN compromise attacks
2. **Privacy**: No third-party CDN tracking or analytics
3. **Reliability**: No dependency on external CDN availability
4. **Performance**: Can be served from same origin, reducing DNS lookups

## Libraries

| Library | Version | File | Purpose |
|---------|---------|------|---------|
| HTMX | 2.0.10 | `checktick_app/static/js/htmx.min.js` | Dynamic HTML updates without JavaScript |
| SortableJS | 1.15.7 | `checktick_app/static/js/sortable.min.js` | Drag-and-drop reordering |
| axe-core | 4.11.3 | `checktick_app/static/js/axe-core.min.js` | WCAG accessibility testing |
| NHS Frontend | 8.1.0 | `checktick_app/static/css/nhsuk-frontend.min.css` | NHS design system styling |
| ReDoc | 2.5.2 | `checktick_app/static/js/redoc.standalone.min.js` | OpenAPI interactive documentation |

## SRI Hashes

Current SRI hashes (SHA-384):

### HTMX 2.0.10

```text
sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V
```

### SortableJS 1.15.7

```text
sha384-DgmC6Xe2bSN2WjTDXzWYbUbxyhNP+NNkGDR/g78pCXV7E7rcVTGxVg0uIVCUUcBc
```

### axe-core 4.11.3

```text
sha384-ZCC+CzYtmcQl5Kc3P96iEgc7ws4aLd064TkQUd85k5wACc0i4CLl7+O5YLV+R9fq
```

### NHS Frontend 8.1.0

```text
sha384-qWZYzCDfWOMmbbg+HoBYKha59es/145h5uc93F1rxBFwJVruD2lcomcIwUlCwPDF
```

### ReDoc 2.5.2

```text
sha384-70P5pmIdaQdVbxvjhrcTDv1uKcKqalZ3OHi7S2J+uzDl0PW8dO6L+pHOpm9EEjGJ
```

## Automatic Updates

GitHub Actions workflows automatically check for updates:

- **Weekly Check**: Runs every Monday at 9:30am UTC
- **Hash Verification**: Compares local files against CDN sources
- **Version Check**: Alerts when newer versions are available
- **PR Creation**: Creates PRs when files need updating

### Workflows

| Workflow | File | Schedule |
|----------|------|----------|
| CDN Libraries | `.github/workflows/update-cdn-libraries.yml` | Monday 9:30am UTC |


## Manual Update Process

### 1. Download Latest Version

```bash
# HTMX
curl -o checktick_app/static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js

# Alternative: npm pack (recommended for reproducibility)
# npm pack htmx.org@2.0.10 && tar -xzf htmx.org-2.0.10.tgz -C /tmp && \
#   cp /tmp/package/dist/htmx.min.js checktick_app/static/js/htmx.min.js && rm htmx.org-2.0.10.tgz

# SortableJS
curl -o checktick_app/static/js/sortable.min.js https://cdn.jsdelivr.net/npm/sortablejs@1.15.7/Sortable.min.js

# Alternative: npm pack (recommended for reproducibility)
# npm pack sortablejs@1.15.7 && tar -xzf sortablejs-1.15.7.tgz -C /tmp && \
#   cp /tmp/package/Sortable.min.js checktick_app/static/js/sortable.min.js && rm sortablejs-1.15.7.tgz

# axe-core
curl -o checktick_app/static/js/axe-core.min.js https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.11.3/axe.min.js

# Alternative: npm pack (recommended)
# npm pack axe-core@4.11.3 && tar -xzf axe-core-4.11.3.tgz -C /tmp && \
#   cp /tmp/package/axe.min.js checktick_app/static/js/axe-core.min.js && rm axe-core-4.11.3.tgz

# NHS Frontend
curl -o checktick_app/static/css/nhsuk-frontend.min.css https://cdn.jsdelivr.net/npm/nhsuk-frontend@8.1.0/dist/nhsuk.min.css

# Alternative: npm pack (recommended)
# npm pack nhsuk-frontend@8.1.0 && tar -xzf nhsuk-frontend-8.1.0.tgz -C /tmp && \
#   cp /tmp/package/dist/nhsuk.min.css checktick_app/static/css/nhsuk-frontend.min.css && rm nhsuk-frontend-8.1.0.tgz

# ReDoc (npm pack recommended - no unpkg/cdnjs alternative needed)
npm pack redoc@2.5.2 && tar -xzf redoc-2.5.2.tgz -C /tmp && \
  cp /tmp/package/bundles/redoc.standalone.js checktick_app/static/js/redoc.standalone.min.js && \
  rm redoc-2.5.2.tgz
```

### 2. Generate SRI Hash

```bash
openssl dgst -sha384 -binary FILE.js | openssl base64 -A
# For CSS files:
openssl dgst -sha384 -binary FILE.css | openssl base64 -A
```

### 3. Update Templates

Update the `integrity` attribute in the relevant templates:

**HTMX** - `checktick_app/templates/base.html`:

```html
<script src="{% static 'js/htmx.min.js' %}"
        integrity="sha384-NEW_HASH_HERE"
        crossorigin="anonymous"></script>
```

**SortableJS** - Multiple templates:

- `checktick_app/surveys/templates/surveys/detail.html`
- `checktick_app/surveys/templates/surveys/builder.html`
- `checktick_app/surveys/templates/surveys/groups.html`
- `checktick_app/surveys/templates/surveys/group_builder.html`

```html
<script src="{% static 'js/sortable.min.js' %}"
        integrity="sha384-NEW_HASH_HERE"
        crossorigin="anonymous"></script>
```
**NHS Frontend** - Survey templates with NHS styling enabled:

- `checktick_app/surveys/templates/surveys/detail.html`
- `checktick_app/surveys/templates/surveys/builder.html`
- `checktick_app/surveys/templates/surveys/groups.html`
- `checktick_app/surveys/templates/surveys/dashboard.html`

```html
<link href="{% static 'css/nhsuk-frontend.min.css' %}"
      integrity="sha384-NEW_HASH_HERE"
      crossorigin="anonymous"
      rel="stylesheet" />
```
### 4. Test

Before deploying:

- [ ] Survey form submissions work (HTMX)
- [ ] Question reordering works (SortableJS)
- [ ] No console errors or CSP violations

## Upgrading Versions

When upgrading to a new major/minor version:

1. Update version numbers in `.github/workflows/update-cdn-libraries.yml`
2. Run the workflow manually or download files
3. Generate and update SRI hashes
4. Review changelog for breaking changes
5. Test thoroughly in development
6. Update this documentation

## Security Considerations

- **SRI verification** ensures files haven't been tampered with
- **Same-origin serving** eliminates CDN trust requirements
- **Version pinning** prevents unexpected updates
- **Weekly monitoring** alerts to new versions and security fixes

## Troubleshooting

### SRI Hash Mismatch

If a library fails to load with "SRI mismatch":

1. Re-download the file from the CDN
2. Regenerate the SRI hash
3. Update the template with new hash
4. Clear browser cache and test

### CDN Unavailable

Since files are self-hosted, CDN outages don't
| NHS Frontend | jsdelivr.net | unpkg.com |affect the application. If you need to re-download:

1. Check CDN status (unpkg, jsDelivr)
2. Try alternative CDN source
3. Use npm to download: `npm pack htmx.org@2.0.10`

## CDN Sources

| Library | Primary CDN | Alternative |
|---------|-------------|-------------|
| HTMX | unpkg.com | jsdelivr.net |
| SortableJS | jsdelivr.net | unpkg.com |
| axe-core | cdnjs.cloudflare.com | unpkg.com |
| ReDoc | npm registry (redoc) | cdn.redoc.ly |

## CI Source-of-Truth (npm)

Our GitHub Actions workflow now uses `npm pack` as the canonical source-of-truth when updating self-hosted JavaScript libraries. Instead of directly curling files from third-party CDNs, the workflow:

- Uses `npm pack <package>@<version>` to retrieve the package tarball from the registry
- Extracts the packaged assets into a temporary directory
- Locates the appropriate `*.min.js` file (for example, `axe-core.min.js`)
- Computes the SHA-384 SRI from the exact bytes in the packed artifact
- Atomically moves the file into `checktick_app/static/js/` and cleans up the temp files

This approach ensures that the file we ship is identical to the npm registry artifact, avoids leaving temporary files in the repository root, and produces reproducible SRI hashes.

## Using the updater script

We provide a small helper script at the repository root to make manual updates safe and reproducible: `s/update-cdn-assets` (no file extension).

- Requirements: `node` and `npm` available on PATH, `openssl` and `tar` on PATH, `python3` for template patching.
- Location: `s/update-cdn-assets`

Usage examples:

Dry run (preview changes, no file writes):
```bash
s/update-cdn-assets --dry-run
```

Interactive update (pick a package, confirm):
```bash
s/update-cdn-assets
```

Non-interactive update (accept prompts automatically):
```bash
s/update-cdn-assets --yes
```

What the script does when updating:

- Lists configured packages and shows the current version (from this document) and the latest on npm
- Downloads the package via `npm pack` into a temp dir and extracts it
- Locates the expected minified asset and copies it atomically into `checktick_app/static/js/`
- Computes the SHA-384 SRI and updates matching templates' `integrity` attributes (best-effort)
- Appends a single-line entry to `docs/compliance/vulnerability-patch-log.md` describing the change

Notes & pitfalls:

- Package layout varies: if the script cannot find the minified file it will print the list of `*.min.js` files found in the package so you can inspect and copy manually.
- The script updates a small set of templates by default. Extend the `templates` list in the script if you have other locations where the script tag appears.
- The script updates `docs/compliance/vulnerability-patch-log.md` automatically when not in `--dry-run` mode. It does not yet update `docs/cdn-libraries.md` automatically — we recommend manually bumping the version and SRI in this document or running the script and then editing the docs to match.
