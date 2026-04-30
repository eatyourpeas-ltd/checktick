# AGENTS.md

This file is a quick start for AI coding agents working in this repository.
It signposts common workflows and links to the full docs instead of duplicating them.

## Primary References

- Project documentation index: `docs/README.md`
- Contributing guide: `CONTRIBUTING.md`
- CDN/SRI update process: `docs/cdn-libraries.md`
- Testing guides: `docs/testing-webapp.md`, `docs/testing-api.md`, `docs/accessibility.md`

## Common Agent Workflows

### 1. Run tests (default for feature/bug-fix work)

- Use `s/test --no-a11y`.
- Accessibility tests require a separate environment and should not be part of the default local validation path.

### 2. Test fallback when Docker is not running

- If `docker compose` web container is not running, use `s/test --no-a11y --host-fallback`.
- This runs tests locally via Poetry when container execution is unavailable.

### 3. Lint before commit

- Any feature or bug fix must be completed by running `s/lint` before committing.

### 4. Bump package version before PR

- For dependency updates, bump `package.json` `version` using semver (`major`/`minor`/`patch`) before raising a PR.

## Dependencies

- For self-hosted JavaScript dependency and SRI updates, use `docs/cdn-libraries.md` as the source of truth.
- Follow the `npm pack` + SHA-384 SRI workflow in `docs/cdn-libraries.md` (or use `s/update-cdn-assets` where appropriate) when bumping JS packages.
- Always record dependency/security patch updates in `docs/compliance/vulnerability-patch-log.md` (sometimes referred to as patch vulnerability logs) with date, version change, and verification notes.

## Notes

- Keep changes minimal and scoped to the request.
- Prefer existing scripts in `s/` over ad-hoc commands when available.
