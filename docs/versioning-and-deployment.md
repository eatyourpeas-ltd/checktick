---
title: Versioning and Deployment
category: development
priority: 12
---

This guide defines how CheckTick versions are managed and when container images are published.

## Version Source of Truth

- The canonical application version is in `pyproject.toml` under `[tool.poetry].version`.
- README version badges are derived from this value.
- Agents and maintainers should not use `package.json` for application versioning decisions.

## Container Registry

- Registry: `ghcr.io/eatyourpeas-ltd/checktick`
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

## When to bump (and when not to)

The version names the **shipped container image**. `Dockerfile.registry` copies
`checktick_app`, `docs`, `locale`, and the packaging files — nothing else — so:

- **Bump** when the merge must ship: application code, templates, static
  assets, dependencies, locale.
- **Don't bump** for maintainer-only surface that never enters the image:
  `s/` ops scripts, `k8s/` manifests, `.github/` workflows. Docs are in the
  image but inert; let them ride the next release unless they must ship now.

`decide-release` keys on a `pyproject.toml` diff, so an unbumped merge
publishes nothing and deploys nothing. That absence **is** the deployment
flag — there is no separate one to set. If an unbumped change later needs
to ship, bump on its own or use the manual dispatch.

## Why This Policy Exists

- Allows maintenance/docs merges to `main` without forcing a new container image.
- Keeps semantic tags aligned with explicit version intent.
- Preserves manual release control when needed.

## Typical Release Flow

1. Bump version in `pyproject.toml` (semver).
2. Merge PR to `main`.
3. Publish workflow applies versioned tags to GHCR.
4. Publish workflow triggers the [Deploy (Civo)](../.github/workflows/deploy-civo.yml) workflow with the versioned tag (deploy trigger swapped from the previous platform's webhook at migration close-out — runbook Phase 6).
5. The Deploy workflow runs the pre-deploy Job (migrations + idempotent syncs) pinned to the same tag, then rolls the web Deployment to the versioned image with zero downtime — `/healthz` readiness gates traffic — and finally rolls every CronJob in the namespace to the same tag (CronJobs are not part of the Deployment rollout and would otherwise keep their manifest pin and drift).

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
