---
title: Civo Kubernetes Operations
category: development
priority: 13
---

# Civo Kubernetes Operations

Operational reference for running CheckTick on managed Kubernetes (Civo, London LON1).
The durable knowledge here was extracted from the Northflank → Civo migration
(production cutover 2026-11-03). The migration runbook and its session log
were removed at close-out (2026-11-06) — the permanent historical record
lives in
[`docs/compliance/infrastructure-technical-change-log.md`](compliance/infrastructure-technical-change-log.md),
with the full documents preserved in git history.

For a walkthrough of the manifests and day-to-day validation commands, see
[`k8s/README.md`](../k8s/README.md).

## Cluster Overview

- Managed k3s on Civo, UK London (LON1) — UK-sovereign hosting for a medical application
- Node pools: **2× `g4s.kube.large`** (pools `large2` + `large3`, ~$87/mo) since
  2026-11-08 — the 1-large+2-medium layout was redesigned because the
  ~1.1 GiB/node platform tax is 47% of a medium and drove a week of
  placement crises; nodes idle ~48–60%. The log-collector DaemonSet is
  **LIVE**. **DB + Vault PVCs are on `civo-volume` (provider-managed
  block storage); Longhorn serves only the RWX trio
  (media/SNOMED/OpenObserve) at 2 replicas.**
- Production namespace `checktick`; **staging (`staging.checktick.uk`) runs in the SAME namespace** — see [Staging environment](#staging-environment) below
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

## Staging environment

Staging (`staging.checktick.uk`) runs in the **same `checktick` namespace** as
prod — deliberately, so it shares the namespace-scoped `checktick-media` +
`checktick-snomed-data` RWX PVCs (SNOMED arrives free, no re-import) and the
Vault (`VAULT_ADDR` + AppRole shared; the `vault-airgap` policy admits
`app=checktick-staging-web` alongside the prod web pods). Stood up
2026-11-08 — apply order and runbooks in [`k8s/README.md`](../k8s/README.md) →
Staging environment:

- **Web**: `deploy/checktick-staging-web` — 1 replica, **no PDB** (a
  single-replica PDB would veto every voluntary drain) and **no topology
  spread** (pointless at 1 replica; a stale `app=checktick-web` selector
  would count PROD pods). Deployed manually via `kubectl set image` after
  re-running the staging migrate Job at the same tag. `DATABASE_URL` comes
  from the `STAGING_DATABASE_URL` key of `checktick-secrets` (an `env`
  entry overrides the shared `envFrom`); `ENVIRONMENT=staging` labels the
  JSON logs (kept OUT of OpenObserve — see Logs below); `SITE_URL` comes
  from `STAGING_SITE_URL` in the config overlay so emailed links point at
  staging, never prod.
- **DB**: `checktick-staging-db` (CloudNativePG, **1 instance, no
  ScheduledBackup, no WAL archiving** — staging data is disposable) on
  `civo-volume`, with its own `checktick-staging-db-ingress` NetworkPolicy.
  The staging batch label is `checktick.io/staging-db-client`, deliberately
  NOT the prod `checktick.io/db-client` grant: prod CronJobs must never
  reach the staging DB, and staging jobs must never reach the prod DB.
- **Cron**: exactly ONE staging CronJob — `prune-unconfirmed-users-staging`
  (same 02:40 slot as prod, different database). `EMAIL_BOUNCE_PROCESSING_ENABLED=false`
  keeps the shared prod mailbox out of staging's pruning, and it has **no
  healthchecks.io ping** (a staging run must never mark prod's check seen).
  The Deploy workflow's roll-every-CronJob step DOES re-image it on prod
  releases — intended: it runs the app image, exactly like its prod twin.
- **Seeding**: `k8s/staging-migrate-job.yaml` (Job `checktick-staging-predeploy` —
  a distinct name from the prod pre-deploy Job the workflow manages) run
  once per staging release.
- **Ingress**: `staging.checktick.uk` → service `checktick-staging-web`, in
  the git-ignored `k8s/ingress.local.yaml` (the cert is unchanged since the
  POC).
- **SSO**: no new credentials — the same Google/Azure client IDs + secrets
  are shared (`checktick-config-local` + `checktick-secrets`); the only
  console-side addition is the redirect URI
  `https://staging.checktick.uk/oidc/callback/` in both consoles.
  `settings.py` derives the OIDC redirect base from `SITE_URL`/
  `STAGING_SITE_URL` (previously hardcoded to `https://checktick.uk` in
  every non-DEBUG env — fixed 2026-11-08; effective from the next image
  release, since settings ship inside the image). hCaptcha sitekeys are
  hostname-bound — add `staging.checktick.uk` to the sitekey's hostnames in
  hCaptcha console if signup captcha will be exercised on staging.
  **Billing**: `settings.py` selects the GoCardless API by `ENVIRONMENT` —
  only `production` uses the live API; development AND staging use the
  sandbox (CTO decision 2026-11-08; the former `DEBUG`-based rule sent
  staging checkout to the live API, since staging runs `DEBUG=False`).
  Effective from the next image release — the deployed 0.27.0 still
  carries the old rule, so do not test billing on staging until it ships.
  Sandbox checkout needs `PAYMENT_PROCESSING_SANDBOX_API_KEY` (+
  `PAYMENT_PROCESSING_SANDBOX_WEBHOOK_SECRET`) in `checktick-secrets`.
- **Logs**: staging stdout is deliberately NOT shipped to OpenObserve —
  the collector's `Exclude_Path` drops every `*staging*` container log
  (web, cron and the staging CNPG pod) so the prod `default/default`
  stream stays unmixed (CTO decision 2026-11-08: separate streams; a
  dedicated staging stream was considered and skipped — it would need a
  second tail input + output on every node). Staging logs stay viewable
  via `kubectl logs`; containerd keeps them on the node. The records
  shipped between staging going live (~11:45 UTC) and the exclusion
  applying (~12:50 UTC) remain in the stream — purge via the OpenObserve
  UI (search `kubernetes.pod_name` matches `*staging*`, then Delete) if
  wanted.
- **Capacity** (measured 2026-11-08): staging adds ~600 Mi steady / 1.5 GiB
  requests (web 512 Mi + db 1 Gi) against ~2–2.8 GiB actually free per node
  on the 2× `g4s.kube.large` layout — comfortable, no resize.

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
   headroom before adding any per-node workload (found live 2026-11-05).
   **Standing decision (2026-11-06, CTO — k8s/POC-STATUS.md session 15): pool
   resize to `g4s.kube.large` is DEFERRED** while real users number 1–2
   ($65→$130/mo not justified; the tolerated risk is availability, never
   data). All three nodes are back in service (`8ciwh` uncordoned). **Updated
   2026-11-07 (CTO): ladder step 1 GO — ONE node to `g4s.kube.large` via a
   second pool + 2× medium (~$86/mo) to unblock the OpenObserve log
   collector** (runbook: Node Pool Resize below); 3× Large remains the
   sustained-growth step. **Ladder step 1 EXECUTED + REDISTRIBUTED
   2026-11-07** (see Node Pool Resize — final steady state ~45%/68%/76%, the
   primary on the large node after a clean operator-coordinated switchover);
   the collector DaemonSet stays OFF pending the trimmed-footprint
   decision. **No per-node DaemonSet until `kubectl top node` headroom is
   verified on every node.**
6. Public hostnames are owned by the **config overlay** via `ALLOWED_HOSTS_EXTRA`
   (k8s/config.env → checktick-config-local), which settings.py appends on top
   of the in-cluster ALLOWED_HOSTS. The web Deployment's env entry carries only
   the in-cluster hosts (pod IP + service names), so `kubectl apply -f
   k8s/web.yaml` / `-k k8s/` can never 400 the public site. (Shipped in 0.25.0.)
   **Interim live env patch RETIRED 2026-11-08** — the documented sequence
   executed: overlay verified → `web.yaml` re-applied → both hostnames
   verified green through the ingress → `k8s/scratch-allowhosts-patch.yaml`
   deleted. Two lessons from the retirement: (a) re-applying `web.yaml`
   against a rolled-forward deployment needs the LIVE tag sed-substituted —
   the manifest pin (`0.25.3`) vs the last-applied annotation (`0.24.2`)
   would have three-way-merged the image BACKWARDS (live was `0.27.0`);
   (b) the "apply wipes scratch patches" rule is precise only for patches
   that modify apply-managed fields (the env VALUE — reverted); affinity
   patches added via `kubectl patch` SURVIVE applies (verified live — the
   web large-pool preference came through the re-apply untouched). Re-applying
   the affinity patches after a manifest re-apply remains the safe habit.

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

## Node Pool Resize (1 Large + 2 medium — log-collector enabler)

**Decision (2026-11-07, CTO): ladder step 1 GO** — 3× `g4s.kube.medium`
(~$65/mo) → ONE `g4s.kube.large` in a **second pool** + 2× medium (~$86/mo),
to create the per-node headroom the log collector DaemonSet needs
(`k8s/log-collector.yaml`: 128 Mi request / 256 Mi limit per node). The
collector stays OFF until the go/no-go below. civo CLI syntax (v1.5.5):
`node-pool ls / instance-ls / create / instance-delete / scale`.

1. **Pre-flight (read-only)**: `s/k8s-backup-verify` green; `kubectl top
   node` baseline; `civo kubernetes node-pool ls <cluster>` → original pool
   ID; `kubectl get pods -A -o wide` → pick the retire target: a medium
   hosting **neither** `vault-0` (a drain re-seals Vault → 503 + unseal
   ceremony) **nor** the CNPG primary (else accept the ~40 s switchover
   blip, rehearsed 2026-11-04). Take a fresh CNPG base backup, as before
   each recycle.
2. **Add the large node**: `civo kubernetes node-pool create <cluster>
   --name large -n 1 -s g4s.kube.large`; wait `kubectl get nodes` Ready.
   The new node joins schedulable (Civo pools carry no taints).
   ⚠ **civo CLI ≤ v1.5.5 PANICS on `--name` under 6 chars** (`slice bounds
   out of range [:6]`) — AFTER the API call succeeds, so the pool IS
   created. Verify with `civo kubernetes node-pool ls <cluster>` before
   retrying, or a duplicate pool bills twice (found live 2026-11-07 — a
   retry after the panic created a second large pool; deleted via
   `civo kubernetes node-pool delete <cluster> <pool-name> -y`).
   Upgrade the CLI or use a ≥6-char pool name to avoid the panic.
3. **Rebalance**: cordon + drain the chosen medium (`kubectl drain <node>
   --ignore-daemonsets --delete-emptydir-data`) — its pods land on the
   large node; Longhorn rebuilds replicas (600 s replenishment interval).
4. **Retire it**: `civo kubernetes node-pool instance-delete <cluster>
   -p <original-pool-id> -i <instance-id>` (alternative: `node-pool scale
   <cluster> <pool-id> -n 2` — check with `instance-ls` which instance
   each path removes first). Verify the floating IP settled on a
   surviving node (~2 min of 404s expected):
   `curl -sf https://checktick.uk/healthz`.
   ⚠ 2026-11-07 pre-flight found the resize target is ALSO the
   floating-IP holder AND the node that restart-storms on every web
   rollout (99% memory) — retire it promptly after the drain; do not
   leave a cordoned 4th node running.
5. **Post-change verification** (standing rules): `s/k8s-backup-verify`
   again; Longhorn volumes back to 3 replicas; `/healthz` fully ok.
6. **GO/NO-GO for the collector**: `kubectl top node` — **every** node
   needs ≥ ~400 Mi headroom (the 2026-11-05 rule: the collector adds
   ~150–250 Mi/node). NO-GO → use its footprint trims (⚠ header in
   `k8s/log-collector.yaml`) or defer to 3× Large.
7. **GO**: `kubectl apply -f k8s/log-collector.yaml` (out-of-band — never
   `apply -k k8s/`), `kubectl -n checktick rollout status ds/log-collector`,
   then port-forward OpenObserve (`5080:5080`) and confirm live logs land
   in stream `default/default` (search the last 5 minutes). Watch
   `kubectl top node` overnight — rollback is deleting the DaemonSet
   (the 2026-11-05 stabiliser that worked).
8. **Record**: §2c row in the [Infrastructure Technical Change
   Log](compliance/infrastructure-technical-change-log.md) with measured
   timings; flip the collector wording here (Monitoring, backlog item 4)
   and the ⚠ header in `k8s/log-collector.yaml` to applied-live.

**Executed 2026-11-07 (measured timings):** pre-flight green (backup chain +
fresh base backup `pre-pool-resize-20261107` 17:47:48Z). Retire target
`…-b966-8ciwh` (floating-IP holder + CNPG replica — the only node hosting
neither `vault-0` nor the primary): cordoned + drained 17:48, instance
deleted 17:49, floating IP re-announced on the large node automatically;
CNPG 2/2 throughout (no switchover — primary untouched); backup chain
re-verified green. **The 404 window ran ~4–5 min (17:49–17:54), NOT the ~2
min the recycle path predicts**: the drain evicts the Longhorn RWX
share-manager for `checktick-media` too — both web pods died on the NFS
blip and their replacements stalled `Init:0/2` on `FailedMount …
DeadlineExceeded` until the share-manager rebuilt on the large node.
All three volumes returned to healthy robustness by ~18:05. **Post-resize
layout defeated the resize's intent: requests-based packing + the web
anti-affinity put ONE web pod on EACH medium → 88%/88% working set while
the large node idles at ~52–55% — collector go/no-go FAILED.** Options
on the table were (a) pin OpenObserve to the large node + nudge one web
pod there (→ mediums ~70–75%, collector GO), (b) 3× large at sustained
growth (~$162/mo), (c) hold. Also caught: civo CLI ≤ v1.5.5 panics on
`--name`
under 6 chars AFTER the API call succeeds — verify with `node-pool ls`
before retrying or you double-bill a duplicate pool.

**Redistribution (same day, ~18:25–18:40 UTC) — option (a) executed:**
git-ignored scratch patches (the `scratch-allowhosts` pattern — any
`apply -k k8s/` WIPES them; re-apply after):
- `k8s/scratch-cronpool-affinity-patch.yaml` — ALL 14 CronJobs hard-pinned
  to `kubernetes.civo.com/civo-node-pool=large` (every batch Django boot
  lands on the roomy node; mediums never see cron spikes)
- `k8s/scratch-openobserve-affinity-patch.yaml` — OpenObserve → `large`
- `k8s/scratch-web-affinity-patch.yaml` — web soft-PREFERS `large`
  (weight 100; the hard `topologySpreadConstraints` in web.yaml still
  force one replica per node, so steady state is always large + one
  medium — the preference only picks WHICH nodes win)
During the web rollout the boot spike on the primary's medium tripped
db-1's status probe → **CNPG operator coordinated a CLEAN switchover to
db-2 (exit 0, ~40 s, data-safe — the rehearsed 04/11 path; WAL chain
unbroken, backup chain re-verified green)**: the primary now runs on the
large node. Final placement: large = web + primary + OpenObserve +
crons (~45%), f985n = web + vault (~68%), hwp2f = db-1 replica +
operator + tax (~76%). Lesson: web replica moves are deterministic ONLY
while the primary's node stays cordoned until the replacement is Ready
(a timed uncordon let one replacement land back on it).
**Collector verdict at this layout: the TRIMMED footprint (~100 Mi/node)
takes the mediums to ~79–80% — the edge of the 11-05 storm band — and the
full footprint does not fit. Keep it OFF until watched overnight, or GO
trimmed + overnight `kubectl top node` watch + rollback
(`kubectl delete ds`) ready.**

**Redesign to 2× large (executed 08/11, ~09:30–10:30 UTC):** the 1L+2M
layout still left the mediums at 76–89% — the CTO approved 2×
`g4s.kube.large` at the same ~$87/mo. Executed: pool `large2` created
(CLI quirk: `node-pool scale` rejects the 5-char `large` pool ID —
create a ≥6-char pool instead), `hwp2f` retired (zero impact), `f985n`
retired with the rehearsed Vault re-seal ceremony, medium pool deleted.
**INCIDENT: `civo kubernetes node-pool delete` for the medium pool ALSO
deleted the `large` pool** (third CLI ID bug — the empty pool name in
the response was the tell); Civo tore down `mbuc5` (repeated re-cordons
+ pod deletions); recovered via pool `large3` (~5 min to a replacement
node; all HA pairs rescheduled; floating IP auto-moved; **no data loss —
DB + Vault are on `civo-volume`, not Longhorn**). **CLI RULE: verify with
`node-pool ls` before AND after every `civo` pool operation; prefer the
Civo dashboard for pool deletions; three CLI ID bugs are now documented
(create panic on <6-char names, scale rejecting <6-char IDs, delete
hitting the wrong pool).** Also this window: cilium-operator lease
patched 15s→90s (item 12); Longhorn volumes set to 2 replicas (2-node
reality); web re-spread one-per-node after a rollout left both replicas
collapsed on one node (topology spread is evaluated at scheduling time,
not end-state — check placement after every web rollout).

**Overnight 07→08/11:** a ~06:05 UTC blip liveness-killed BOTH web pods
(their replacements coin-flipped again — the large-pool preference
cannot help the SECOND replica, the spread constraint forbids it) and one
landed back on `hwp2f` → 91% → 07:15/07:30 readiness blips on the fresh
pod (DB connect EPERM, then a cluster-wide DNS outage — `coredns` was a
SINGLE replica on `hwp2f`; when that node stalls, in-cluster AND
external resolution fail everywhere; the 07:30 "Vault is sealed" healthz
line was a FALSE ALARM from this — Vault stayed unsealed throughout).
Fixes: web re-moved off `hwp2f` (cordon dance), `coredns` scaled to 2
replicas (hwp2f + mbuc5). **Standing hazard: after ANY web pod churn,
check placement (`kubectl get pods -l app=checktick-web -o wide`) — the
second replica coin-flips between the mediums and `hwp2f` cannot host it.**

**Morning 08/11 — collector apply + rollback + root-cause fix (found
live):** overnight BOTH RWX volume engines (media + SNOMED) + their
share-managers drifted from the large node onto `f985n` (+~250 Mi →
82%), which liveness-killed its web pod at 08:38 — BEFORE any collector.
The trimmed collector then passed the headroom gate (all nodes ≥ ~400 Mi
free) and shipped 526,717 records / ~324 MB to OpenObserve in ~20 min —
but at 89% `f985n` killed the web pod again, so the documented rollback
fired. **Fix executed 09:00 UTC: both engines moved back to the large
node** (cordon both mediums → delete the two share-manager pods → they
reschedule to the large node → uncordon; ~3 min user-visible NFS/404
window, web pods replaced cleanly, healthz 200, volumes back to healthy
robustness, backup chain re-verified green). **Collector re-applied
09:06 UTC — LIVE and shipping; steady state large 53% / f985n 82% /
hwp2f 78%.** The tail DBs are hostPath-persistent, so the backlog drain
RESUMED from 11-05 21:35 (no duplicate re-ship of the 526,717 records
already ingested); live logs appear in the stream once the remaining
~2.5-day backlog drains (~30 min). Overnight watch + rollback
(`kubectl -n checktick delete ds log-collector`) per the runbook.

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
  operator's age private key (Bitwarden). The restore chain is proven
  end-to-end — CT-03 in
  [`restoration-test-log.md`](compliance/restoration-test-log.md)
  (2026-11-06). The pre-migration alternative
  (stop-copy-restart on a cron) would put unseal shares on a scheduled job
  and breaks the custody model — do not use it.
- **2026-11-08 incident (found + fixed same morning):** the deploy
  workflow's roll-every-CronJob step set the out-of-band `vault-snapshot`
  job's `upload` container to the app image (no aws CLI) → the 03:45
  nightly failed `aws: not found` (both backoff attempts; no upload, no HC
  ping — healthchecks.io alerts on the missed ping). Live image restored;
  manual re-run completed 08:06 UTC
  (`vault-raft-2026-11-08T080625.tar.age`); `deploy-civo.yml` now skips
  `vault-snapshot` in the roll. The init containers (hashicorp/vault,
  alpine) were untouched — the roll only covers `containers`, which is
  why the job reached the upload step before dying.
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
  DaemonSet (`k8s/log-collector.yaml`): **applied 2026-11-08 with the
  trimmed footprint, rolled back the same morning** — it shipped
  526,717 records / ~324 MB in ~20 min (proof the pipeline works), but
  f985n had drifted ~250 Mi heavier overnight (both RWX engines +
  share-managers landed there) and liveness-killed its web pod with the
  collector aboard → the documented rollback (`kubectl -n checktick
  delete ds log-collector`) fired. Re-apply after the engine move (Node
  Pool Resize). It stays out of `kustomization.yaml` so `kubectl apply
  -k k8s/` can never silently recreate it. The Platform Admin log-viewer
  API (`HOSTING_*`) is an unrelated opt-in feature.

## Hardening Backlog

Moved from the migration runbook's Phase 6 list; in rough priority order
(`ALLOWED_HOSTS_EXTRA` shipped in 0.25.0 and is off the list):

1. ~~**Vault storage backup** — Raft migration + nightly snapshot CronJob~~
   **DONE 2026-11-06** — migration executed, snapshot pipeline live, and
   the restore test PASSED (CT-03,
   [`restoration-test-log.md`](compliance/restoration-test-log.md))
2. **Barman Cloud Plugin migration** before any CNPG operator upgrade past 1.30
3. TLS on the in-cluster Vault endpoint (cert-manager) + `VAULT_TLS_VERIFY=true`
4. ~~OpenObserve + collector DaemonSet for infrastructure log retention~~ —
   **DONE 2026-11-08**: OpenObserve deployed (2026-11-05, NF-era history
   restored); collector LIVE since 09:06 UTC 2026-11-08 (trimmed profile,
   after the resize + the engine-move fix — Node Pool Resize above); see
   the ⚠ note in `k8s/log-collector.yaml`
5. Least-privilege ServiceAccount kubeconfig for the deploy workflow (today it is
   cluster-admin)
6. Longhorn recurring snapshots on `checktick-media`; Velero/PVC backups
7. k3s Secrets encryption-at-rest (verify feasibility); non-root Vault
   (`runAsUser: 100`); staging namespace separation; alerting on `/healthz`
8. Open SNOMED readers as `file:...?mode=ro&immutable=1` (needs an image release;
   non-urgent given the init-container conversion)
9. Quarterly restore rehearsal — step-by-step procedure in
   [docs/restore-rehearsal.md](restore-rehearsal.md)

## Open Items from the Retired Migration Records (2026-11-06)

The migration session records (`k8s/POC-STATUS.md`, the Northflank→Civo runbook,
`docs/vault-raft-migration.md`) were retired at close-out — the durable posture
lives in this document and the compliance folder, full history in git. Items
they left **open**, carried here so nothing is lost with them:

1. **Vault rekey** — `vault operator rekey` on the migrated Vault (Shamir 3-of-4,
   operator ceremony; also decide the share medium) + revoke the drill API token.
   Nothing records it as done; keys were minted pre-migration.
2. **Clinical-safety docs review** — `docs/clinical-safety/*` still carry
   Northflank-era live-state claims ("hosted on Northflank infrastructure",
   "Northflank SLA 99.9%") that are now factually wrong; assessment records, so
   they need a deliberate review pass, not an automated sweep.
3. **OpenObserve root password** is still the Northflank-era credential — rotate
   in the UI (`kubectl -n checktick port-forward svc/openobserve 5080:5080`)
   and update the `openobserve-auth` Secret.
4. **Graph email 403s — ROOT-CAUSED 2026-11-08** (probe via
   `k8s/scratch-graph-diag.py`, git-ignored): `Mail.Send` IS granted (token
   roles claim verified) and plain sends from the `admin@checktick.uk`
   mailbox succeed (HTTP 202). The 403 is **`ErrorSendAsDenied`**: Django's
   `AdminEmailHandler` sends error mail **from `SERVER_EMAIL`
   (`server@checktick.uk`)**, the backend then sets an explicit Graph
   `from`, and `server@` is NOT an alias of the sending mailbox — so every
   error-alert email is rejected while all user-facing mail (from
   `DEFAULT_FROM_EMAIL` = admin@) works. Fix (M365 admin, ~30 s): add
   `server@checktick.uk` as an **alias** of the admin@ mailbox, or set
   `SERVER_EMAIL=admin@checktick.uk` in `k8s/config.env` → recreate the
   `checktick-config-local` ConfigMap. Verify by re-running the probe
   (expect probe B → 202). **VERIFIED 2026-11-08: alias added → probe B
   **VERIFIED 2026-11-08: alias added → probe B
   202 — the Django error-email alerting path is live again; revisit
   item 5 (the ERROR-email storm) before the next outage.** `Mail.Read`
   (application) consented + verified same day — token roles
   `['Mail.Read', 'Mail.Send']`, `fetch_bounce_messages` reads the inbox
   (0 NDRs in the 24h window, as expected for current traffic). Gotcha
   found on the way: the first add was the DELEGATED `Mail.Read` —
   invisible to the client-credentials flow, which only sees APPLICATION
   permissions (hence "admin consent required: No" with nothing to
   grant). Remaining: the Exchange Online ApplicationAccessPolicy scoping
   `Mail.Read` to the sending mailbox (see access-control.md §12).
5. **AdminEmailHandler emails on every ERROR log** — an outage (a healthz 503
   loop) turns into an outbound-email storm that amplifies load. **FIX
   WRITTEN 2026-11-08** (ships with the next release):
   `AdminEmailRateLimitFilter` (`checktick_app/core/logging/
   admin_email_rate_limit.py`) — one admin email per 15 min window
   (env `ADMIN_EMAIL_RATE_LIMIT_SECONDS`, 0 = off), mounted on the
   `mail_admins` handler only; dropped records still reach stdout/
   OpenObserve. Until the release: filter them in the mail client.
6. **Traefik access logging is OFF** — no request-level logs, only internal
   CRD-watch noise; a monitoring gap worth a deliberate decision.
7. **`s/k8s-vault-unseal` stdin piping is broken** on this kubectl ("Unseal
   submission failed") — use the interactive form
   `kubectl -n checktick exec -it vault-0 -- vault operator unseal`; port the
   captured-output verification pattern (see the ceremony scripts) into it
   before relying on the non-interactive path.
8. **Nothing schedules `s/k8s-backup-verify`** — a stuck non-terminal Backup
   silently blocks the nightly schedule (the 2026-11-04 outage); the runner is
   read-only and exit-coded, so wire it to cron/CI for the "phase != completed
   after 02:10 UTC" check, and keep running it after any cluster intervention.
9. **The raft peer registers as `127.0.0.1:8201`** — the migrate helper's
   loopback `cluster_addr`; harmless while single-node, revisit if a raft peer
   is ever added.
10. **`logs.checktick.uk` is a STALE Northflank-era DNS record** (found
   2026-11-07): the Namecheap CNAME still points at
   `…dns.northflank.app` → a Northflank LB returning 503 — it has been
   dead since the 2026-11-03 cutover, it does NOT route to Civo. The
   OpenObserve instance on Civo is healthy and ClusterIP-only BY DESIGN
   (port-forward to reach it). Action: delete the DNS record — or, if a
   public logs UI is ever wanted, that is a deliberate decision requiring
   an ingress route + cert AND rotating the still-Northflank-era root
   password (item 3) first.
11. **`LOGS_BASE_URL`/`LOGS_ORGANIZATION`/`LOGS_STREAM_NAME` are stale
   Northflank-era values** (found 2026-11-07): `http://openobservelogs:5080`
   (no such service on Civo — it is `openobserve`) and org/stream
   `prod_logs` (the Civo instance serves `default`/`default`). Dormant — no
   `HOSTING_*` keys are set, so the Platform Admin log-viewer feature is
   off — but update `k8s/config.env` before ever enabling it.
12. **cilium-operator CrashLoopBackOff — ROOT CAUSE of the 08/11 DNS
     blips + email storm (pre-existing since 04/11):** both replicas
     fatal with `"Leader election lost"` (75/83 restarts by 09:20 UTC,
     08/11) — the lease (`cilium-operator-resource-lock`) has
     `leaseDurationSeconds: 15` and renewals land at the 14 s edge, so
     any API latency spike kills the holder. Millisecond correlation
     with app failures: operator stop 09:11:10.520Z → first web-pod DNS
     failure 09:11:10.863Z; each crash cycle blips in-cluster DNS/
     service routing for ~1–2 min (cilium v1.18.4, in-cluster API
     endpoint 192.168.1.2:6443). cnpg-controller-manager (~119 restarts)
     and civo-ccm (~86) churn the same way — all lease-based, pointing
     at intermittent API-server latency from the worker nodes. Lease
     reset attempted 09:16 UTC (deleted the resource-lock; re-acquired,
     then lost again). **ACTION: Civo support ticket (managed control
     plane + CNI) — evidence bundle in the ops session log 08/11;
     interim: the item-5 email rate-limit makes the blips quiet.**
     **INTERIM FIX APPLIED 08/11 09:53 UTC: cilium-operator
     leader-election lease patched 15s→90s**
     (`--leader-election-lease-duration=90s
     --leader-election-renew-deadline=60s
     --leader-election-retry-period=5s` on the kube-system deployment —
     Civo-managed, may be reverted by their reconciliation; re-apply if
     the churn returns). Operators stable since (0 restarts vs a crash
     every 5–15 min); the DNS blips and their error-email storms
     stopped. The Civo ticket should cover BOTH the lease root cause
     AND the CLI's wrong-pool delete (see Node Pool Resize).

## Related

- [`k8s/README.md`](../k8s/README.md) — manifest walkthrough and validation commands
- [`docs/self-hosting-scheduled-tasks.md`](self-hosting-scheduled-tasks.md) — CronJob reference
- [`docs/infrastructure-logging.md`](infrastructure-logging.md) — structured logging
- [`docs/versioning-and-deployment.md`](versioning-and-deployment.md) — release flow
- [`.github/workflows/deploy-civo.yml`](../.github/workflows/deploy-civo.yml) — deploy pipeline
