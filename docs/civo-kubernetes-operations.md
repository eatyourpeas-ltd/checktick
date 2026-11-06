---
title: Civo Kubernetes Operations
category: development
priority: 13
---

# Civo Kubernetes Operations

Operational reference for running CheckTick on managed Kubernetes (Civo, London LON1).
The durable knowledge here was extracted from the Northflank → Civo migration
(production cutover 2026-11-03); the migration runbook and its session log were
retained only until Phase 6 close-out and then removed. The permanent historical
record of the migration lives in
[`docs/compliance/infrastructure-technical-change-log/`](compliance/infrastructure-technical-change-log/).

For a walkthrough of the manifests and day-to-day validation commands, see
[`k8s/README.md`](../k8s/README.md).

## Cluster Overview

- Managed k3s on Civo, UK London (LON1) — UK-sovereign hosting for a medical application
- Production namespace `checktick`; staging (`staging.checktick.uk`) runs on the same cluster
- Components:
  - web Deployment (image pinned to a published release tag, never `latest`)
  - CloudNativePG PostgreSQL 17 — `checktick-db` cluster (primary + one replica), in-cluster
  - HashiCorp Vault — single-replica StatefulSet (`vault-0`), integrated
    Raft storage on a PVC (migrated from file storage 2026-11-06)
  - Traefik ingress (443 only) + cert-manager TLS
  - Longhorn volumes: `checktick-media`, `checktick-snomed-data`
  - 13 CronJobs (scheduled tasks — see [`docs/self-hosting-scheduled-tasks.md`](self-hosting-scheduled-tasks.md))
- Backups: CNPG `ScheduledBackup` (nightly 02:00 UTC base backup) + continuous WAL
  archiving to Civo Object Store (UK region), **120-day retention** per the
  [Backup & Data Retention Policy](compliance/backup-policy.md); nightly
  ENCRYPTED Vault raft snapshots (03:45 UTC, 14-snapshot retention — see
  Vault Operations below)
- Deploys: GitHub Actions *Deploy (Civo)* workflow (pre-deploy Job runs migrations +
  idempotent syncs pinned to the same tag, then a `maxUnavailable: 0` rolling update
  gated on `/healthz`). Migrations must stay expansion/contract — a rolled-back
  rollout briefly runs the previous image against the new schema.

## Critical Safety Rules

1. **Never `vault operator init` on migrated/restored Vault storage.** A fresh init
   makes every encrypted survey in PostgreSQL permanently undecryptable. Restore the
   storage directory first, then unseal with the EXISTING shares.
2. **Vault and PostgreSQL move together or not at all.** Never roll back one
   component alone.
3. **Major PostgreSQL upgrades go via dump/restore with the TARGET version's
   binaries** — never `pg_upgrade` in place, and never dump with newer binaries
   than the restore target.
4. **Probe rules: never point liveness OR startupProbe at `/healthz`.** A
   deep-probed startup gate restart-loops the web pods every 150 s while the
   Vault is sealed — restarts cannot fix a seal (found live 2026-11-05 when
   the interim Vault backup's sealed window took the site down; both probes
   now use the trivial `/api/health`, which itself 500s if the DB is
   unreachable — DRF's throttle cache is DB-backed).
5. **A ~2 GiB node is a full node.** The smallest node ran primary DB + CNPG
   operator + traefik (floating IP) + longhorn + a web pod at ~79% of
   requests; adding one small DaemonSet (~150–250 Mi/node) caused
   memory-reclaim stalls that liveness-killed EVERY pod on the node in
   lockstep, including the primary. Stabilisation that worked: cordon → CNPG
   auto-switchover → move Deployment pods off. Verify `kubectl top node`
   headroom before adding any per-node workload (POC-STATUS session 12).
6. Public hostnames are owned by the **config overlay** via `ALLOWED_HOSTS_EXTRA`
   (k8s/config.env → checktick-config-local), which settings.py appends on top
   of the in-cluster ALLOWED_HOSTS. The web Deployment's env entry carries only
   the in-cluster hosts (pod IP + service names), so `kubectl apply -f
   k8s/web.yaml` / `-k k8s/` can never 400 the public site. *(Shipped in 0.25.0;
   until that release is deployed, a live Deployment env patch —
   `k8s/scratch-allowhosts-patch.yaml`, git-ignored — still carries the public
   hosts and any manifest re-apply must be followed by re-applying the patch.)*
   Post-release retirement: apply the overlay, re-apply web.yaml, verify
   checktick.uk + staging respond, then delete the scratch patch.

## Node Maintenance (kernel / node-image upgrades)

Proven during the CVE-2026-98432 patch window (2026-11-04):

- **`civo k8s upgrade` is IN-PLACE** — it swaps the k3s binary only (~4 min) and does
  **not** re-image the nodes. One API `ServiceUnavailable` blip + a transient
  `degraded` healthz while the k3s daemon bounces. The node image and kernel are
  unchanged by it.
- **`civo k8s recycle CLUSTER --node NODE` is the image path**: cordon + drain →
  DELETE the instance → build a fresh node from the current image (~4–8 min each;
  the PVC reattach dominates). Serial per node — never recycle two at once.
- **The external IP is a cluster-managed floating IP.** When the node holding it is
  deleted, Civo moves the IP to a surviving node automatically. Across a full
  3-node recycle it never changed (no kubeconfig / DNS / Namecheap changes needed) —
  but **verify after every recycle**.
- **Expect ~2 minutes of 404s after each recycle** while the floating IP settles and
  the new node's traefik syncs its routers — a fresh traefik answers TLS on the IP
  before it has the ingress routes. Self-heals; do not panic.
- Take a CNPG base backup before each recycle. Draining the primary's node triggers
  a CNPG switchover (~40 s, healthz degraded→ok) — data-safe because the operator
  coordinates it via each instance's status API (see the NetworkPolicy note below).
- After any node loss, Longhorn RWX volumes serve from **one surviving replica**
  until replenishment completes (600 s `replica-replenishment-wait-interval`);
  both volumes returned to 3 replicas a few minutes after the last recycle.

## CNPG (PostgreSQL) Operations

- **The db-ingress NetworkPolicy must allow the CNPG operator to reach the
  instances on port 8000 (status API) as well as 5432.** Without it:
  `Instance Status Extraction Error` on the Cluster and
  `Cannot extract Pod status ... :8000: i/o timeout` every ~4 s in the operator log —
  and draining the primary's node STALLS against the `checktick-db-primary` PDB.
- **Verify the backup chain after ANY intervention** (node recycles, operator
  restarts, schedule changes — this caught two real outages). The runner is
  **`s/k8s-backup-verify`** (read-only, exits non-zero on any failed check);
  it performs all of the following:
  1. `kubectl get scheduledbackups -n checktick` — schedule armed,
     `nextScheduleTime` in the future
  2. `kubectl get backups -n checktick` — every row must be terminal
     (`completed`/`failed`). A **stuck non-terminal Backup silently blocks the
     whole schedule** (delete it to unblock)
  3. Check the scheduled backup's status for a **dead pod IP** — a backup pinned
     to a deleted pod's IP never runs
  4. `ContinuousArchiving=True` on the Cluster; WAL chain unbroken in the object store
- **Before any CNPG operator upgrade past 1.30**: migrate backups from the in-tree
  Barman object store to the **Barman Cloud Plugin** — in-tree support is removed
  in 1.31 and the operator emits a deprecation warning on every reconcile.
- Restore path: latest base backup + WAL archive from Civo Object Store into a
  fresh CNPG cluster. Step-by-step procedure: [Quarterly Restore
  Rehearsal](restore-rehearsal.md), run by **`s/k8s-restore-rehearsal`**;
  results feed
  [`docs/compliance/restoration-test-log.md`](compliance/restoration-test-log.md).
- Post-restore Vault ceremony (generate-root, fixed-policy verification,
  AppRole mint, token revoke): **`s/k8s-vault-ceremony`** (drill pod by
  default; production requires an explicit `--pod vault-0` + confirmation).

## Vault Operations

- After node loss, `vault-0`'s storage reattaches in ~5.5 min and the pod comes up
  `Initialized: true, Sealed: true` — **storage survives; do not re-init.** Unseal
  with 3-of-4 production shares (**`s/k8s-vault-unseal`** — hidden prompts only,
  shares never appear on a command line); healthz is fully ok ~10 s later.
- **Storage backup: nightly ENCRYPTED raft snapshots — LIVE since 2026-11-06.**
  A 03:45 UTC CronJob (`k8s/vault-snapshot.yaml`, applied out-of-band) logs
  in via a least-privilege AppRole (`sys/storage/raft/snapshot` only — no
  unseal shares ever touch a scheduled job), runs
  `vault operator raft snapshot save`, wraps the snapshot with `age` using
  the operator's public key, and uploads to `s3://checktick-backups/vault/`
  (retain 14). The stored object needs BOTH the Shamir shares AND the
  operator's age private key (Bitwarden). The runbook is
  [`docs/vault-raft-migration.md`](vault-raft-migration.md) (executed
  2026-11-06; the restore test closes it). The pre-migration alternative
  (stop-copy-restart on a cron) would put unseal shares on a scheduled job
  and breaks the custody model — do not use it.
- `tls_disable = true` in-cluster is the migration baseline; the backlog adds
  cert-manager TLS on the in-cluster endpoint + `VAULT_TLS_VERIFY=true`.
- The Vault container image defaults to root — pin `runAsUser: 100` (backlog).

## Monitoring & Alerting

- **StatusCake** (5-minute polling) on `https://checktick.uk/healthz` — returns 503
  if Vault is sealed, the database is unreachable, or SNOMED is misconfigured.
- **healthchecks.io** per-CronJob pings: each CronJob pings its `HC_PING_*`
  capability URL only on success (`command && curl ...`), so a failed *or
  non-running* job triggers an email alert. The URLs live in the git-ignored
  `k8s/config.env` (`checktick-config-local` ConfigMap) and never enter the repo.
  Unset = no ping (self-hosters are unaffected).
- **OpenObserve** (self-hosted, `k8s/openobserve.yaml`): log retention layer
  for the app's structured stdout JSON
  ([Infrastructure Logging](infrastructure-logging.md)). ClusterIP only —
  reach the UI with `kubectl -n checktick port-forward svc/openobserve
  5080:5080`; credentials in the `openobserve-auth` Secret
  (see `k8s/openobserve.example.env`). Org `default` / stream `default`
  carries the exported Northflank-era archive (June 2026 week — the
  in-app exporter only ran that long) and would carry live logs; 180-day
  stream retention per the
  [Logging & Audit Policy](compliance/logging-policy.md). The collector
  DaemonSet (`k8s/log-collector.yaml`) is built but **deliberately not
  applied** — it tipped the smallest node over its memory wall on
  2026-11-05 (POC-STATUS session 12); redeploy only after node-pool resizing
  or reworking its footprint. The Platform Admin log-viewer API
  (`HOSTING_*`) is an unrelated opt-in feature.

## Hardening Backlog

Moved from the migration runbook's Phase 6 list; in rough priority order
(`ALLOWED_HOSTS_EXTRA` shipped in 0.25.0 and is off the list):

1. ~~**Vault storage backup** — Raft migration + nightly snapshot CronJob~~
   **DONE 2026-11-06** (migration executed + snapshot pipeline live; closes
   fully when the restore test passes — see Vault Operations)
2. **Barman Cloud Plugin migration** before any CNPG operator upgrade past 1.30
3. TLS on the in-cluster Vault endpoint (cert-manager) + `VAULT_TLS_VERIFY=true`
4. ~~OpenObserve + collector DaemonSet for infrastructure log retention~~ —
   OpenObserve is deployed (2026-11-05, NF-era history restored); the
   collector awaits node-pool sizing — see the ⚠ note in
   `k8s/log-collector.yaml`
5. Least-privilege ServiceAccount kubeconfig for the deploy workflow (today it is
   cluster-admin)
6. Longhorn recurring snapshots on `checktick-media`; Velero/PVC backups
7. k3s Secrets encryption-at-rest (verify feasibility); non-root Vault
   (`runAsUser: 100`); staging namespace separation; alerting on `/healthz`
8. Open SNOMED readers as `file:...?mode=ro&immutable=1` (needs an image release;
   non-urgent given the init-container conversion)
9. Quarterly restore rehearsal — step-by-step procedure in
   [docs/restore-rehearsal.md](restore-rehearsal.md)

## Related

- [`k8s/README.md`](../k8s/README.md) — manifest walkthrough and validation commands
- [`docs/self-hosting-scheduled-tasks.md`](self-hosting-scheduled-tasks.md) — CronJob reference
- [`docs/infrastructure-logging.md`](infrastructure-logging.md) — structured logging
- [`docs/versioning-and-deployment.md`](versioning-and-deployment.md) — release flow
- [`.github/workflows/deploy-civo.yml`](../.github/workflows/deploy-civo.yml) — deploy pipeline
