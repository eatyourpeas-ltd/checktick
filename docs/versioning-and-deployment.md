---
title: Versioning and Deployment
category: api
priority: 12
---

This guide defines how CheckTick versions are managed and when container images are published.

## Version Source of Truth

- The canonical application version is in `pyproject.toml` under `[tool.poetry].version`.
- README version badges are derived from this value.
- Agents and maintainers should not use `package.json` for application versioning decisions.

## Container Registry

- Registry: `ghcr.io/eatyourpeas/checktick`
- Primary tags:
  - `latest`
  - `X.Y.Z` (full semantic version)
  - `X.Y` (minor stream)
  - SHA-based development tags

## Publish Triggers

The Docker publish workflow runs under controlled conditions:

1. **Tag push** matching `v*` (release-style publish)
2. **Manual dispatch** via workflow input
3. **Push to `main` with `pyproject.toml` changed** (version-aware publish)

If none of these conditions are met, publish is skipped.

## Why This Policy Exists

- Allows maintenance/docs merges to `main` without forcing a new container image.
- Keeps semantic tags aligned with explicit version intent.
- Preserves manual release control when needed.

## Typical Release Flow

1. Bump version in `pyproject.toml` (semver).
2. Merge PR to `main`.
3. Publish workflow applies versioned tags to GHCR.
4. Northflank restarts and pulls latest published image.

## Accidental No-Bump Merges

If code is merged without a version bump:

- CI still runs.
- Container publish is skipped unless trigger conditions are met.
- You can still publish intentionally using manual dispatch or by creating a `v*` tag.

## Related References

- [CDN Libraries](cdn-libraries/)
- [Contributing](../CONTRIBUTING.md)
- [Documentation System](documentation-system/)
- [Infrastructure Technical Change Log](compliance/infrastructure-technical-change-log/)
- [Vulnerability Patch Log](compliance/vulnerability-patch-log/)
