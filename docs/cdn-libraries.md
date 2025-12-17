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
| axe-core | 4.11.0 | `checktick_app/static/js/axe-core.min.js` | WCAG accessibility testing |

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

### axe-core 4.11.0

```text
sha384-C9AUAqw5Tb7bgiS/Z+U3EGEzD+qn2oE0sJOC4kp0Xu8DcQMLKECMpbVsuWxF+rdh
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

# SortableJS
curl -o checktick_app/static/js/sortable.min.js https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js

# axe-core
curl -o checktick_app/static/js/axe-core.min.js https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.11.0/axe.min.js
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
