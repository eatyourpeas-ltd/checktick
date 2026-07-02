---
title: CDN Libraries
category: security
priority: 10
---

CheckTick self-hosts critical frontend libraries and enforces Subresource Integrity (SRI).

## Why self-host?

1. **Security**: SRI hashes verify file integrity and mitigate CDN compromise risk.
2. **Privacy**: no third-party CDN tracking.
3. **Reliability**: no runtime dependency on external CDN availability.
4. **Performance**: same-origin serving can reduce connection overhead.

## Single source of truth

CDN asset metadata is maintained in:

- `checktick_app/cdn_assets.json`

This includes each asset's:

- package name
- pinned version
- static target file path
- source path inside the npm package
- SRI hash

Templates read SRI values from this manifest via template context (`cdn_assets.*.sri`), so hashes are no longer duplicated in template files.

## Libraries

<!-- CDN_LIBRARIES_TABLE:START -->
| Library | Version | File | Purpose |
| ------- | ------- | ---- | ------- |
| HTMX | 2.0.10 | `checktick_app/static/js/htmx.min.js` | Dynamic HTML updates without JavaScript |
| SortableJS | 1.15.7 | `checktick_app/static/js/sortable.min.js` | Drag-and-drop reordering |
| axe-core | 4.12.1 | `checktick_app/static/js/axe-core.min.js` | WCAG accessibility testing |
| ReDoc | 2.5.3 | `checktick_app/static/js/redoc.standalone.min.js` | OpenAPI interactive documentation |
| NHS Frontend | 8.1.0 | `checktick_app/static/css/nhsuk-frontend.min.css` | NHS design system styling |
<!-- CDN_LIBRARIES_TABLE:END -->

## SRI hashes

Current SHA-384 SRI values:

<!-- CDN_SRI_HASHES:START -->
### HTMX 2.0.10

```text
sha384-q2oWHKMnJry5BOtYUZkXcyieUmqzXIjdmKDYicmMspegPENZr4UrGc656JYEgJoo
```

### SortableJS 1.15.7

```text
sha384-pAVIuzMQbJcj7JX9XYTtp8sSNh3OvFXn0g9ldX+lANHPoXFdYVKw/2G1gS/eU62A
```

### axe-core 4.12.1

```text
sha384-JQegRXq6EhTiWoGPFDmqbJNsDow5BoSsGhnaeDzGp+qyOFCuMZZ24qY2fz3FxZF5
```

### ReDoc 2.5.3

```text
sha384-wGl2vRYcqJBa50CzY6euuShOQuBMr6jGCJwEZd2GpPR6Ht+9GDtNpAPpA5QAr7GJ
```

### NHS Frontend 8.1.0

```text
sha384-IDDaUjZThM1cVGH55y4Yzz7YTgr55yuHEQYOnf3Hx0jpArWS5CgFIKTnSl6CHKbx
```
<!-- CDN_SRI_HASHES:END -->

> The two sections above are generated from `checktick_app/cdn_assets.json` by `s/sync-cdn-docs`.

## Automation

### Workflow

| Workflow | File | Schedule |
| --- | --- | --- |
| CDN libraries check | `.github/workflows/update-cdn-libraries.yml` | Monday 9:30am UTC |

### Updater scripts

- `s/update-cdn-assets` — update one asset from npm, refresh manifest SRI/version, sync docs, append compliance log.
- `s/sync-cdn-docs` — regenerate docs sections from the manifest only.

## Manual update process

Preferred path:

```bash
s/update-cdn-assets
```

Useful modes:

```bash
# preview only
s/update-cdn-assets --dry-run

# non-interactive update of a specific asset
s/update-cdn-assets --yes --key axe_core

# sync docs from manifest without changing assets
python3 s/sync-cdn-docs
```

## Upgrading versions

When upgrading a CDN library:

1. **Update from one place**: use `s/update-cdn-assets` (or edit `checktick_app/cdn_assets.json` directly if needed).
2. **Sync generated docs**: `python3 s/sync-cdn-docs` (automatically run by `s/update-cdn-assets`).
3. **Record compliance entry**:
   - security/CVE-driven: `docs/compliance/vulnerability-patch-log.md`
   - routine non-security maintenance: `docs/compliance/infrastructure-technical-change-log.md`

Then run validation (`s/test --no-a11y`) before PR.

## Troubleshooting

### SRI mismatch

If a library fails to load due to SRI mismatch:

1. Re-download via `npm pack` (or rerun `s/update-cdn-assets`).
2. Recompute/update hash in `checktick_app/cdn_assets.json`.
3. Sync docs with `python3 s/sync-cdn-docs`.
4. Clear browser cache and re-test.

### CDN unavailable

Because assets are self-hosted, runtime app availability is unaffected by CDN outages.

## CDN sources

| Library | Primary source | Alternative |
| --- | --- | --- |
| HTMX | unpkg.com | jsdelivr.net |
| SortableJS | jsdelivr.net | unpkg.com |
| axe-core | cdnjs.cloudflare.com | unpkg.com |
| ReDoc | npm registry (redoc) | cdn.redoc.ly |
| NHS Frontend | jsdelivr.net | unpkg.com |
