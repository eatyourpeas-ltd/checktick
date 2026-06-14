# AGENTS.md

This file is a quick start for AI coding agents working in this repository.
It signposts common workflows and links to the full docs instead of duplicating them.

## Primary References

- Project documentation index: `docs/README.md`
- Contributing guide: `CONTRIBUTING.md`
- CDN/SRI update process: `docs/cdn-libraries.md`
- Versioning and deployment policy: `docs/versioning-and-deployment.md`
- Testing guides: `docs/testing-webapp.md`, `docs/testing-api.md`, `docs/accessibility.md`

## Common Agent Workflows

### 1. Run tests (default for feature/bug-fix work)

- Use `s/test --no-a11y`.
- If the Docker web container is not running, the script will start it automatically.
- Accessibility tests require a separate environment and should not be part of the default local validation path.

### 2. Test fallback when Docker is not running

- If the Docker web container is not running, the script will start it automatically.
- `s/test --no-a11y --host-fallback` runs via Poetry on the host, but **requires a local PostgreSQL instance on port 5432**. The Docker DB is not exposed to the host, so this will fail unless you have a separate local DB. The script will check and exit clearly if none is found.

### 3. Lint before commit

- Any feature or bug fix must be completed by running `s/lint` before committing.

### 4. Version bumps (CTO/maintainer workflow)

- The Python package version lives in `pyproject.toml` (not `package.json`).
- When `pyproject.toml` version is bumped and merged to `main`, GitHub Actions automatically:
  - Updates the version badge in `README.md`
  - Enables versioned container publishing via the Docker publish workflow rules
  - These appear in the [GitHub Packages Registry](https://github.com/eatyourpeas-ltd/checktick/pkgs/container/checktick)
- See `docs/versioning-and-deployment.md` for full trigger and tagging rules.
- Typically bumped by CTO; agents should follow semver conventions if contributing version changes.

## CDN / Self-Hosted JS Dependencies

- **Single source of truth:** `checktick_app/cdn_assets.json` holds the version, SRI hash, npm package name, static file path, and source path for every self-hosted CDN asset.
- Templates read SRI and file path from this manifest via the `cdn_assets` template context variable (injected by `checktick_app/context_processors.py` → `checktick_app/cdn_assets.py`). **Do not hardcode SRI hashes or static file paths in templates.**
- To update a CDN dependency, run `s/update-cdn-assets`. This downloads the asset from npm, copies it into `checktick_app/static/`, updates the manifest version and SRI, regenerates `docs/cdn-libraries.md`, and appends a compliance log entry.
- Useful flags:
  - `s/update-cdn-assets --dry-run` — preview only.
  - `s/update-cdn-assets --yes --key axe_core` — non-interactive update of a specific asset.
  - `s/update-cdn-assets --sync-docs` — regenerate docs from the manifest without downloading anything.
- `s/sync-cdn-docs` (also called automatically by the updater) regenerates the auto-generated table and SRI sections inside `docs/cdn-libraries.md` from the manifest.
- The GitHub Actions workflow (`.github/workflows/update-cdn-libraries.yml`) reads pinned versions from the manifest (not from `env:` variables) and writes updated SRI hashes back to the manifest via `jq`.
- **When bumping a CDN library version, only two things are needed:**
  1. Run `s/update-cdn-assets` (handles manifest, static file, docs, and compliance log).
  2. If the update is security-driven, also add a row to `docs/compliance/vulnerability-patch-log.md`.
- See `docs/cdn-libraries.md` for the full architecture and troubleshooting guide.

## Other Dependencies

- Python dependencies are managed via Poetry (`pyproject.toml` / `poetry.lock`).

## Notes

- Keep changes minimal and scoped to the request.
- Prefer existing scripts in `s/` over ad-hoc commands when available.
