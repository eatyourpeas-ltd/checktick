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

### 2. Run tests without Docker

- Use `s/test --no-a11y --host-fallback` to run locally via Poetry, bypassing Docker entirely.

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

## Dependencies

- For self-hosted JavaScript dependency and SRI updates, use `docs/cdn-libraries.md` as the source of truth.
- Follow the `npm pack` + SHA-384 SRI workflow in `docs/cdn-libraries.md` (or use `s/update-cdn-assets` where appropriate) when bumping JS packages.
- Record routine (non-security) dependency/library updates in `docs/compliance/infrastructure-technical-change-log.md` under "Application Dependency Maintenance (Non-Security)".
- Record CVE/security remediations in `docs/compliance/vulnerability-patch-log.md` with date, version change, and verification notes.

## Notes

- Keep changes minimal and scoped to the request.
- Prefer existing scripts in `s/` over ad-hoc commands when available.
