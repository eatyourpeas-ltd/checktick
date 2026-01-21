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
| HTMX | 1.9.12 | `checktick_app/static/js/htmx.min.js` | Dynamic HTML updates without JavaScript |
| SortableJS | 1.15.2 | `checktick_app/static/js/sortable.min.js` | Drag-and-drop reordering |
| axe-core | 4.11.1 | `checktick_app/static/js/axe-core.min.js` | WCAG accessibility testing |

## SRI Hashes

Current SRI hashes (SHA-384):

### HTMX 1.9.12

```text
sha384-EfwldhYywH4qYH9vU8lMn+pd6pcH0kGpPUVJuwyHnj/5felkkIUVxf1wMAEX7rCY
```

### SortableJS 1.15.2

```text
sha384-x9T5uN6arBCGAt3RJPa+A5l/6KQXb0UC7Eig1DxZI+EekZYlD+5S+EEJ+U2lebod
```

### axe-core 4.11.1

```text
sha384-CEnpkh+ndCKp9F6zlTFMCy3ebmIfIj+HyBbO4hxQz4bVQNq+Id1MPxPF6cZ4QzPA
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
curl -o checktick_app/static/js/htmx.min.js https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js

# Alternative: npm pack (recommended for reproducibility)
# npm pack htmx.org@1.9.12 && tar -xzf htmx.org-1.9.12.tgz -C /tmp && \
#   cp /tmp/package/dist/htmx.min.js checktick_app/static/js/htmx.min.js && rm htmx.org-1.9.12.tgz

# SortableJS
curl -o checktick_app/static/js/sortable.min.js https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js

# Alternative: npm pack (recommended for reproducibility)
# npm pack sortablejs@1.15.2 && tar -xzf sortablejs-1.15.2.tgz -C /tmp && \
#   cp /tmp/package/Sortable.min.js checktick_app/static/js/sortable.min.js && rm sortablejs-1.15.2.tgz

# axe-core
curl -o checktick_app/static/js/axe-core.min.js https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.11.1/axe.min.js

# Alternative: npm pack (recommended)
# npm pack axe-core@4.11.1 && tar -xzf axe-core-4.11.1.tgz -C /tmp && \
#   cp /tmp/package/dist/axe.min.js checktick_app/static/js/axe-core.min.js && rm axe-core-4.11.1.tgz
```

### 2. Generate SRI Hash

```bash
openssl dgst -sha384 -binary FILE.js | openssl base64 -A
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

Since files are self-hosted, CDN outages don't affect the application. If you need to re-download:

1. Check CDN status (unpkg, jsDelivr)
2. Try alternative CDN source
3. Use npm to download: `npm pack htmx.org@1.9.12`

## CDN Sources

| Library | Primary CDN | Alternative |
|---------|-------------|-------------|
| HTMX | unpkg.com | jsdelivr.net |
| SortableJS | jsdelivr.net | unpkg.com |
| axe-core | cdnjs.cloudflare.com | unpkg.com |

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
