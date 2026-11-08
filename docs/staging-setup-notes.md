---
title: Staging Setup Notes (temporary signpost)
category: development
priority: 99
---

# Staging Setup Notes — TEMPORARY

> **Throwaway doc** (added 2026-11-08, from the cluster-redesign ops
> session). Captures the DECIDED design + file pointers for the staging
> environment so a fresh session can implement it without re-deriving
> anything. **Delete this file once staging is live.** Not in the docs
> index on purpose.

## Decided design (2026-11-08, CTO)

- **Same namespace (`checktick`)** — PVCs are namespace-scoped, so sharing
  the SNOMED/media volumes requires it. (A separate namespace would need a
  duplicated SNOMED PVC or an export path — deliberately not chosen.)
- **Staging web**: a second Deployment (1 replica) cloned from
  `k8s/web.yaml`, mounting the SAME `checktick-media` +
  `checktick-snomed-data` PVCs, with its own Service.
- **Staging DB**: a second CNPG cluster cloned from `k8s/postgres-cnpg.yaml`
  but trimmed — `instances: 1`, **no ScheduledBackup, no WAL archiving**
  (staging data is disposable). Storage: `civo-volume`, same as prod's.
  Applied out-of-band like the prod one (needs the CNPG operator).
- **Vault**: shared — staging pods use the same `VAULT_ADDR` service
  (HTTP, no volume mount, no new unseal ceremony).
- **CronJobs**: staging gets exactly ONE — `prune-unconfirmed-users`
  (anti-bot signup hygiene; hCaptcha gates signups, the prune mops up
  unconfirmed accounts). Give it staging's `DATABASE_URL` and set
  `EMAIL_BOUNCE_PROCESSING_ENABLED=false` in its env (the bounce phase
  reads the shared prod mailbox — don't cross it into staging's pruning).
  Everything else is prod-only.
- **Seeding**: run the `k8s/migrate-job.yaml` pattern ONCE against the
  staging DB (migrations + idempotent syncs). SNOMED comes free via the
  shared PVC — no re-import.
- **Ingress**: `staging.checktick.uk` currently routes to the PROD web
  service — re-point that host to the staging Service in the git-ignored
  `k8s/ingress.local.yaml` (template: `k8s/ingress.yaml`; the staging cert
  already exists).
- **Capacity** (measured 2026-11-08): ~600 Mi steady (web ~450 + db ~130)
  against 2.1–2.7 GiB free per node on the 2× `g4s.kube.large` cluster —
  comfortable, no resize needed.

## File pointers

| What | Where |
| :--- | :--- |
| Cluster context, pool pins, civo CLI rules | `docs/civo-kubernetes-operations.md` (Node Pool Resize section + the `k8s/scratch-*` affinity patches) |
| Web Deployment to clone | `k8s/web.yaml` |
| CNPG cluster spec to clone + trim | `k8s/postgres-cnpg.yaml` |
| Ingress host to re-point | `k8s/ingress.local.yaml` (git-ignored) |
| Seeding job pattern | `k8s/migrate-job.yaml` |
| The one cron to adapt | `prune-unconfirmed-users` in `k8s/cronjobs.yaml` (reference: `docs/self-hosting-scheduled-tasks.md`) |
| Runtime config overlay | `k8s/config.env` → `checktick-config-local` ConfigMap (`ALLOWED_HOSTS_EXTRA` already carries `staging.checktick.uk`) |
| Staging DB credentials | a staging `DATABASE_URL` in the git-ignored `k8s/secrets.env` (or a staging-scoped Secret) — never committed |
| Prod deploy flow (for contrast) | `.github/workflows/deploy-civo.yml` — staging deploys are manual `kubectl set image` initially |

## Watch-outs carried over from the ops session

- The deploy workflow's roll-every-CronJob step will re-image ANY new
  CronJob's containers on release — keep staging's cron on the app image
  or make it out-of-band (see the vault-snapshot incident, §2c change
  log, 08/11/2026).
- After any staging web rollout, check pod placement — topology spread is
  evaluated at scheduling time, not end-state (both replicas can collapse
  onto one node).
- The civo CLI has three documented ID bugs — see the CLI RULE in
  `docs/civo-kubernetes-operations.md` → Node Pool Resize before touching
  pools.
