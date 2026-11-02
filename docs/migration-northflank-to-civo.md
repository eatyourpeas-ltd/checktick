---
title: Northflank to Civo Migration Runbook
category: development
priority: 13
---

# Northflank to Civo Migration Runbook

Operational runbook for moving the hosted CheckTick production service from
Northflank to Civo (UK, London region). This document contains **no secrets** —
hostnames, credentials, and unseal shares are held out-of-band (password
manager / private ops repo / unseal ceremony).

## Status

Phase 0 (Civo provisioning) is complete — the `checktick` cluster is live and
running the staging POC. **Phase 1 (POC) is COMPLETE:** the round-trip smoke
(`k8s/smoke-test.py`) is 19/19 green, the manifest idempotency check passed
(two consecutive `kubectl apply -k k8s/`: no spec drift, no pod restarts),
and the tear-down → re-apply test passed (full namespace delete, rebuild
from the manifests + out-of-band objects, fresh Vault ceremony, `/healthz`
fully ok, smoke 19/19 re-run on the rebuilt environment). **Phase 2
(credential rotation) is complete:** every provider-level credential is
rotated at its provider and staged in the git-ignored `k8s/secrets.env` /
applied as the `checktick-secrets` Secret — only the two deliberately
cutover-time items remain (new `SECRET_KEY` inside the freeze window; fresh
AppRole credentials on the migrated Vault). Phases 3–6 are next.

## Context

- Provider change driven by the Northflank security incident (credential
  rotation follow-through) and a preference for a UK company on UK
  infrastructure for this medical application.
- Civo runs managed Kubernetes (k3s). CheckTick is deployed as containers to
  GHCR already, so the application artifact is unchanged — only the platform
  layer moves.
- The Civo deployment manifests live in [`k8s/`](../k8s/) (generic, public).
  Environment-specific values and secrets never enter this repository.

## Scope: what moves and how

| Component | Method | Notes |
| :--- | :--- | :--- |
| PostgreSQL | `pg_dump` → `pg_restore` | PostgreSQL 17 (the 16 → 17 upgrade happens during the cutover restore) |
| Vault | Storage-directory copy | **Not** a dump, **not** a re-init. See critical rules below |
| Media volume | Pre-sync + delta `rsync` | Small (admin-uploaded icons) |
| SNOMED CT `snomed.db` | Rebuilt from TRUD | Regenerable by design; never copied |
| Operational logs | Not migrated | Audit trail lives in Postgres and moves with the DB |
| Scheduled tasks | Recreated as CronJobs | See [Scheduled Tasks](self-hosting-scheduled-tasks/) |

**Zero-downtime expectations:** the *first hop* has a maintenance window
measured in minutes (dump/restore dominated). Zero-downtime applies to every
deploy *after* the move, via rolling updates with readiness gates — validated
during the POC.

## Critical safety rules — read before touching anything

1. **Never run `vault operator init` on the target Vault when migrating
   production data.** CheckTick's Vault holds the vault-side partial keys of
   the platform master key and the KEKs that wrap every survey's DEKs
   (split-knowledge model, see [Vault](vault/)). A fresh init mints a new master
   key with no way to merge, and every existing encrypted survey in PostgreSQL
   becomes permanently undecryptable. Migration is a storage-directory copy
   unsealed with the **existing** 3-of-4 Shamir shares. A fresh `init` is only
   correct in the POC, against a throwaway Vault with synthetic data.
2. **Pin the Vault image version** to `hashicorp/vault:1.21.1` (matches source).
   Version upgrades are a separate change, done after the migration settles.
3. **PostgreSQL major version may only move forward** (16 → 17). A logical
   `pg_dump`/`pg_restore` into the same or newer major version is the
   supported upgrade path — restoring into an *older* major is not. Dump
   with the *target's* binaries (postgres:17 image) against the 16 source.
   Civo managed PostgreSQL offers 17/18 only; the cutover therefore performs
   the 16 → 17 upgrade for free. Django 5.2 and psycopg2 2.9 fully support 17,
   and CheckTick uses no Postgres extensions (encryption is Python-side), so
   there are no compatibility blockers. Prefer 17 over 18 (longer track
   record; no feature CheckTick needs from 18).
4. **Never log secrets, request bodies, decrypted survey objects, or database
   row contents** during the migration. All verification is done with counts.
   This extends the standard logging rules to migration tooling and terminals.
5. **Rehearse everything against scratch copies first** and record durations.
   The announced window is the rehearsal measurement plus 50% contingency.
6. **Northflank stays intact (stopped, not deleted)** until the rollback window
   expires. It is the only full backup of the pre-migration state.
7. `PLATFORM_CUSTODIAN_COMPONENT` must never be set in any environment,
   manifest, or secret file — `settings.py` hard-fails if it is. The custodian
   component remains with the custodians, out-of-band, as per the F6
   split-knowledge control.

## Target architecture (summary)

| Component | Target |
| :--- | :--- |
| Web | `Deployment` ×2 (POC) / ×3 (prod), rolling updates `maxUnavailable: 0` |
| Probes | Readiness `/healthz` (deep: DB + Vault + SNOMED); liveness `/api/health` (trivial — never `/healthz`, a sealed Vault must not trigger restart loops) |
| Vault | `StatefulSet`, file storage, manual unseal (3-of-4), NetworkPolicy: ingress only from web pods on 8200, egress denied |
| PostgreSQL | Civo managed DB (or in-cluster CloudNativePG), via `DATABASE_URL` |
| Media | Longhorn RWX PVC at `/app/media` |
| SNOMED | Longhorn RWX PVC; each web pod copies `snomed.db` to a node-local `emptyDir` at boot so SQLite is never opened over NFS |
| Logs | stdout only, collected by the platform (OpenObserve as before) |
| Ingress | Traefik + cert-manager (Let's Encrypt) |
| Scheduled tasks | 13 CronJobs (see [Scheduled Tasks](self-hosting-scheduled-tasks/)) |
| Pre-deploy | `Job`: `migrate`, `createcachetable`, `sync_*` commands |

Manifest details and apply order: [`k8s/README.md`](../k8s/README.md).

## Phase 0 — Civo provisioning (start now)

- [ ] Create Civo Kubernetes cluster: **London (LON1)**, 3 nodes — three
      gives pod anti-affinity and survives a node failure during a rollout.
      **Storage finding (POC):** Civo ships `civo-volume` (CSI block storage,
      RWO) as its only default StorageClass — **no Longhorn**. RWO is correct
      for Postgres data volumes; anything needing `ReadWriteMany` (media,
      SNOMED share) requires Longhorn to be installed explicitly or a design
      change — decision recorded before the web Deployment.
- [ ] **Object store finding (POC):** Civo's object store rejects the
      default payload-checksum mode of modern S3 clients
      (`XAmzContentSHA256Mismatch` on `PutObject`). Every uploading tool
      needs `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and
      `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required` — set on the CNPG
      `spec.env`; the future SNOMED CI upload step and OpenObserve need
      the same pair.
- [ ] **CNPG credential finding (POC):** the `bootstrap.initdb` secret is
      BOOTSTRAP-TIME-ONLY — changing it does NOT change the database
      role's password (auth failures after a secret update). Empty-database
      remedy: delete Cluster + PVCs and re-apply so initdb runs with the
      current secret. For post-cutover rotation, use `spec.managed.roles`
      with `passwordSecret` (continuously reconciled) — verify the schema
      against the installed CRD before relying on it. Cutover itself is
      unaffected: it bootstraps fresh with the current secret.
- [ ] **Byte-count checksums (POC habit):** `openssl rand -hex 24` = 48
      bytes; `DATABASE_URL` for that password = 102 bytes (23-char prefix +
      48 + 31-char suffix). Environments that store env-file values raw
      (kubectl) must never wrap values in quotes, and byte counts are the
      cheapest integrity check after any credential paste.
- [ ] **Probe host-header finding (POC):** kubelet httpGet probes send
      `Host: <pod IP>`, which Django's `ALLOWED_HOSTS` rejects — readiness
      never passes even though the app is healthy. POC fix: the web
      Deployment sets `ALLOWED_HOSTS` via the Downward API (`$(POD_IP)`).
      Proper fix for the next image release: `settings.py` appends an
      `ALLOWED_HOSTS_EXTRA` list so the config overlay owns the public
      domains and the Deployment adds only the pod IP. Northflank never
      surfaced this because its probes used an approved hostname.
- [ ] **TLS posture finding (POC):** on Kubernetes, `SECURE_SSL_REDIRECT`
      must be False at the app — TLS and the http→https redirect belong to
      the ingress (Traefik). App-level redirects hide healthz content behind
      301s and would loop against the ingress's plain-HTTP backend (no
      proxy-header trust is configured in settings). Same posture at
      cutover.
- [ ] **SNOMED build finding (POC):** the in-cluster `update-snomed-db`
      CronJob allocates 8 GiB (the `sct ndjson` step peaks above 4 GiB and
      is OOM-killed with less) — it can NEVER run on the Civo POC nodes
      (3 × 2 vCPU/4 GB). Replacement: build snomed.db on a free GitHub
      16 GB runner (`.github/workflows/build-snomed-db.yml`, `--no-seed`
      because CI has no app database), upload to
      `s3://checktick-backups/snomed`, and import in-cluster with a small
      CronJob (download + atomic rename + `seed_snomed_datasets`).
- [ ] **SNOMED WAL finding (POC):** `sct` builds `snomed.db` with
      `journal_mode=WAL` (db header write/read version = 2), and every app
      reader opens it `mode=ro` (healthz, `snomed_resolver`,
      `seed_snomed_datasets`). A read-only SQLite connection to a WAL
      database must create a `-shm` file — that works wherever the volume is
      mounted read-write (which is why the seed container succeeds on the
      RWX PVC) but fails on the web container's `readOnly: true` emptyDir
      mount with `SQLITE_CANTOPEN` ("unable to open database file", surfaced
      by healthz as `snomed: error` — after a copy the file exists, it just
      cannot be opened). Fix in `k8s/web.yaml`: the `snomed-copy` init
      container (which mounts the emptyDir read-write) runs
      `PRAGMA journal_mode=DELETE` on the POD-LOCAL COPY after `cp` — the
      RWX share is never written, and the read-only web container then opens
      a plain rollback-journal database. Verified end to end:
      `import-snomed-db` job → 1.9 GB copy → conversion → `/healthz`
      `snomed: ok`. App-level alternative for the Phase 6 backlog: open
      `file:...?mode=ro&immutable=1` (skips the shm entirely); would need an
      image release.
- [ ] **Vault AppRole policy gap (POC finding, smoke step 17):** the
      `checktick-app` policy written by `vault/setup_vault.py` grants
      `secret/data/surveys/+/kek`, `organizations/+/master-key`,
      `teams/+/team-key` and read-only `platform/master-key` — but NOT
      `secret/data/users/*`, which is the path family
      `VaultClient.escrow_user_survey_kek` / `recover_user_survey_kek` /
      `verify_user_identity_email` use (`users/<uid>/surveys/<sid>/recovery-kek`).
      Consequence: any recovery-dashboard approval
      (`RecoveryRequest.execute_recovery`) or `execute_platform_recovery`
      run fails at Vault with `permission denied`. NOT Civo-specific — the
      same setup script ran on Northflank, so production carries the same
      gap (recovery escrow was never exercised there either).
      **Fix status:** the policy stanza (`secret/data/users/+/surveys/+/
      recovery-kek` + `secret/metadata/users/*` list/delete) is added to
      `vault/setup_vault.py`, and `k8s/smoke-test.py`
      step 17 exercises the real `users/...` escrow path. **Applied to the
      STAGING Vault** (root ceremony: `vault operator generate-root` with
      3-of-4 shares → `vault policy write checktick-app` → revoke temp
      root) and smoke is **19/19 green**. Applying needs a privileged token
      (the AppRole cannot write policies; the POC root token was revoked
      after setup). Because Vault migrates by storage-directory
      COPY (not re-init), the moved Vault keeps whatever policy the source
      had — the **PRODUCTION** Vault (Northflank) still needs the same
      apply before/after the move, before any recovery approval is
      needed (pre-cutover checklist item, Phase 3).
      Fresh Vaults initialised after the fix get it automatically.
- [ ] **Config overlay precedence finding (POC):** changing a value in the
      committed `web-configmap.yaml` (`checktick-config`) is NOT enough —
      the git-ignored local overlay (`checktick-config-local`, applied from
      `k8s/config.env`) sits later in the envFrom chain and silently
      overrides it. This bit exactly here: the structural ConfigMap said
      `SECURE_SSL_REDIRECT=False` but the overlay still said `True`, so
      pods kept 301-ing plain-HTTP to https and startup probes never went
      green — with a misleading symptom (probe events showed
      `https://<pod-ip>:8000` timeouts because the probe FOLLOWS the 301,
      then the TLS handshake against plain-HTTP gunicorn hangs). Rule:
      when changing any posture key, grep BOTH `web-configmap.yaml` and
      `config.env`; after fixing, re-apply the overlay ConfigMap and
      `rollout restart` (env loads only at container start).
- [ ] **Redirect-cycle finding (POC, APP-LEVEL, fixed in 0.24.0):**
      `Require2FAMiddleware` × the `email_confirmed_required` decorator
      form an infinite redirect cycle for any authenticated password
      user with unconfirmed email and no 2FA device: every page →
      `/2fa/setup/` (middleware) → `core:home` (email gate) →
      `/2fa/setup/` (home not exempt) → … The browser shows "too many
      redirects", and even the emailed confirmation link is bounced
      into the cycle, so the user can never confirm. Reproduced
      mechanically in the live pod (Django test client →
      RedirectCycleError). Staging hit it because Google signup
      auto-logs in with `email_confirmed=False` while confirmation
      delivery was broken (stale creds) — production runs the SAME
      released code and is reachable via the same states, unnoticed
      only because password users there confirm before first login.
      Fix: exempt the real `/2fa/` route (the old `/app/2fa/` entry
      never existed), the `/accounts/confirm-email/` +
      `/accounts/resend-confirmation/` recovery routes, and `/home`;
      `is_password_user` no longer counts OIDC accounts' empty-string
      password as usable (SSO exemption as documented). The anti-bot
      gating is unchanged: unconfirmed users still cannot create
      surveys, and the prune cron is untouched. Regression tests:
      `checktick_app/core/tests/test_2fa_middleware.py`.
- [ ] **SITE_URL finding (POC):** emailed links (email confirmation,
      invitations) are built from `settings.SITE_URL`, so staging must
      set `SITE_URL` to the staging hostname or the links point at
      production where the token does not exist. The Civo overlay
      (`k8s/config.env`) now carries
      `SITE_URL=https://staging.checktick.uk`; cutover flips it back.
- [ ] **OIDC-on-staging finding (POC):** Google signup worked on
      staging using the production client IDs. Resolved (2026-11-02):
      mozilla-django-oidc derives the redirect URI from the request host
      (`absolutify(request, ...)` in both the authorize and token steps),
      so staging sends `https://staging.checktick.uk/oidc/callback/` and
      the SSO loop completes on staging. Both app registrations carry the
      staging URI — Google completes end to end, and the Azure flow gets
      past redirect validation to the token-issuance stage. The hardcoded
      `settings.OIDC_REDIRECT_URI` (prod `OIDC_BASE_URL`) is unused by
      this version of the library — no app change needed.
- [ ] **Azure tenant quote artefact (POC, 2026-11-02):** Microsoft SSO
      failed with `AADSTS900023 … tenant identifier '""'` — the live
      `checktick-secrets` carried `OIDC_OP_TENANT_ID_AZURE` as the literal
      two-character string `""` (quote artefact, same class as the
      `SELF_HOSTED: "False"` value; the key was absent from
      `k8s/secrets.env` entirely, so the Secret was not rebuildable from
      it). The string is truthy, so `settings.py`'s `or "common"` fallback
      never fired and the authorize URL became
      `login.microsoftonline.com/""/oauth2/v2.0/authorize`. Fix (final,
      2026-11-02): the correct value is **`common`**, not the org tenant
      GUID — the Azure registration accepts personal Microsoft accounts
      (production signs in personal M365 accounts), and a tenant-scoped
      authorize endpoint refuses them at claim issuance (`AADSTS90123`:
      an initial pin to the `GRAPH_TENANT_ID` GUID let the user reach the
      Microsoft sign-in page, then Azure denied token issuance for a
      personal M365 account). Live Secret patched to `common`, the key
      added unquoted to `k8s/config.env`, `checktick-config-local`
      re-applied, healthz-gated rollout, authorize endpoint verified 200
      at `common` with the staging redirect URI, and the scratch export
      re-exported so future teardown/restore carries the fixed value.
      Rule: `kubectl --from-env-file` stores values raw — never quote
      values in `secrets.env`/`config.env`. **Cutover note:** when
      production's env moves, its effective tenant value must stay
      `common` — do not "helpfully" pin the org tenant GUID. Follow-ups:
      the four `HOSTING_*` Northflank keys are quote-wrapped stale
      values — drop them at cutover rather than migrating.
- [ ] **Dual-default StorageClass finding (POC, found by the Phase 1
      tear-down test):** the cluster had BOTH `civo-volume` AND `longhorn`
      annotated as default StorageClass, so anything omitting
      `storageClassName` (the CNPG data PVCs, the Vault
      `volumeClaimTemplates`) silently landed on Longhorn instead of the
      documented civo-volume. Longhorn reserves size × 3 replicas per
      volume per node; db (2×10 GiB) + vault (10 GiB) reservations exhausted
      the ~35 GiB free per node, and the RWX media/snomed volumes then failed
      replica scheduling (`ReplicaSchedulingFailure: precheck new replica
      failed: insufficient storage`, volumes `detached/faulted`). Symptom:
      web pods hung `Init:0/2` on FailedAttachVolume and the SNOMED import
      job sat unscheduled for 20+ min looking like a "slow download" —
      a stuck import with zero init-container logs is a volume-attach
      failure, not a network problem. Fix: remove the default annotation
      from `longhorn` (single default = `civo-volume`, matching the comments
      in `web.yaml`/`postgres-cnpg.yaml`), delete + recreate the CNPG cluster
      and Vault, after which the RWX volumes attach immediately and the
      import completes in its normal ~3.5 min. `civo-volume` is RWO — correct
      for single-instance data; only the explicitly-pinned `longhorn` RWX
      claims should ever touch Longhorn on this cluster size.
- [ ] **Apply-order finding (POC, tear-down test):** the
      [`k8s/README.md`](../k8s/README.md) apply order is load-bearing.
      Re-applying in a custom order (CNPG → predeploy → cronjobs → import)
      left `checktick-predeploy` in `CreateContainerConfigError` (its
      `envFrom` ConfigMap `checktick-config` did not exist yet) and the
      import job Pending on a not-yet-created PVC; the 5-min cron also fired
      two Failed ticks into the same window. Rule: config (both ConfigMaps)
      and secrets BEFORE any workload; `web.yaml` BEFORE anything that
      mounts its PVCs.
- [ ] **NetworkPolicy propagation finding (POC):** a freshly created pod
      labelled `app=checktick-web` cannot reach `vault:8200` for the first
      seconds of its life — the CNI has not yet programmed the vault-airgap
      allow rule for the new pod, so connections fail with EPERM
      ("Operation not permitted"), which looks like a policy
      misconfiguration but is not: the same connection succeeds ~15 s
      later. The POC ceremony script
      (`k8s/scratch-vault-ceremony.sh`, git-ignored) retries with backoff.
      Expect the same delay for any freshly created helper pod that talks
      to Vault.
- [ ] **CNPG bootstrap race (POC, minor):** `kubectl wait --for=condition=Ready
      pod/checktick-db-1` errors NotFound until the initdb Job has completed —
      instance pods do not exist during bootstrap. Wait on the cluster
      instead: `kubectl wait --for=jsonpath='{.status.readyInstances}'=2
      cluster/checktick-db`.
- [ ] **Vault init JSON field name (POC, minor):** Vault 1.21.1
      `vault operator init -format=json` emits `unseal_keys_b64`, not the
      older `unseal_keys_b` — ceremony tooling must parse accordingly.
- [ ] Choose the database host (PostgreSQL 17 either way — safety rule 3):
      - **Civo managed PostgreSQL 17** (~$43/mo entry tier): least
        operational burden — backups, upgrades and failover are the
        provider's problem. Confirm automated backups exist and **verify
        the restore procedure once** before it is ever needed.
      - **In-cluster CloudNativePG** (`k8s/postgres-cnpg.yaml`): near-zero
        marginal cost on nodes you already pay for; scheduled base backups
        plus WAL archiving to Civo Object Storage give point-in-time
        recovery, and the operator handles failover. You own Postgres
        operations. Requires the CNPG operator and a tested backup/restore
        drill. The exit path to managed later is another dump/restore — the
        same drill rehearsed here.
      - Either way: network access restricted to the cluster; strong
        generated password; network-restricted endpoint (firewall to cluster
        node egress if public, TLS enforced).

      Current recommendation at this user volume: CloudNativePG, revisiting
      managed when the database becomes business-critical enough that its
      monthly cost is cheaper than the ops attention.
- [ ] Create object storage bucket (backups; future log retention).
- [ ] Store the DB credentials: password manager now; at deploy time they go
      into the Kubernetes Secret via a **local, git-ignored**
      `k8s/secrets.env` (see [`k8s/README.md`](../k8s/README.md)). Never in
      this repository — it is public and the docs are shipped in the image.
- [ ] Request Civo security due-diligence artefacts for the DPIA/processor
      record: DPA (UK GDPR), security posture summary, pen-test evidence,
      sub-processor list, incident-notification commitments.

## Phase 1 — POC (throwaway environment)

Goal: prove the plumbing and **rehearse the migration mechanics** with
synthetic data and a throwaway Vault — not just steady-state running.

- [x] Apply the manifests per [`k8s/README.md`](../k8s/README.md).
- [x] Initialise the throwaway Vault with `vault operator init -key-shares=4
      -key-threshold=3` (rehearse the real ceremony shape) and configure
      AppRole per [Vault](vault/). These shares/keys are disposable.
- [x] Run the pre-deploy Job and the SNOMED build (`update_snomed_db`, needs
      the 8 GiB memory allocation documented in
      [Scheduled Tasks](self-hosting-scheduled-tasks/)). POC variant: the CI
      workflow builds snomed.db on a GitHub runner and the small
      `import-snomed-db` CronJob imports it (see the SNOMED build finding
      below).
- [x] `/healthz` returns full `ok`: DB, Vault unsealed, SNOMED.
- [x] Log in, create a test survey, submit a response, and view/decrypt it —
      the round-trip proves DB + Vault + key hierarchy work together.
      Scripted and green: `k8s/smoke-test.py` (19/19 steps — real login+2FA,
      encrypted create, ECIES submission, password unlock, export decrypt,
      Vault escrow, SNOMED resolver). **Found the Vault AppRole policy gap
      on the way — see the Phase 0 ledger.**
- [x] **Zero-downtime proof:** run `while true; do curl -sf
      https://<host>/healthz >/dev/null || echo FAIL; sleep 1; done` and trigger
      a rolling update (`kubectl set image ...`). Zero FAILs required.
      (The `zdt-test` pod loop: zero FAILs across five rollouts.)
- [x] Re-apply all manifests (`kubectl apply -k k8s/`) and confirm idempotency
      (no spurious restarts).
      **DONE (2026-11-01):** two consecutive applies — the Deployment spec
      converged, its generation stable, no new pods, `vault-0` uptime
      untouched. `vault`/PDB/NetworkPolicy report `configured` on every apply
      but a field-by-field compare shows **zero** spec differences — the
      recurring `configured` is empty-patch metadata churn (generation tick),
      not drift. Signature: only generation moves; `kubectl diff` shows
      nothing but metadata.
- [x] Tear-down test: `kubectl delete -k k8s/` then re-apply from scratch.
      **DONE (2026-11-01):** namespace delete ~5m20s (CNPG decommissioning
      dominates), rebuilt from the four out-of-band objects
      (`checktick-secrets`, `checktick-db-creds`, `checktick-db-backup-creds`,
      `checktick-config-local` — exported first; the Secret is restored
      as-is, it is NOT rebuildable from `k8s/secrets.env` because it alone
      carries `OIDC_OP_TENANT_ID_AZURE`, which `settings.py` reads without a
      default) + CNPG + a FRESH `vault operator init` ceremony (throwaway
      POC only — production is storage-copy, rule 1) + predeploy + SNOMED
      import + ingress + `ALLOWED_HOSTS` scratch patch. Exposed the
      dual-default StorageClass bug on the way (Phase 0 ledger) — which is
      exactly what a tear-down test is for. Verified: `/healthz` fully ok
      via pod / Service DNS / public HTTPS, smoke 19/19 re-run green.

**Exit criteria:** every box above ticked, and the timed steps recorded in
Appendix B. Do not schedule the cutover until then.

## Phase 2 — Credential rotation plan (incident follow-through)

**Status: COMPLETE.** The migration was the completion point for rotating
everything that ever transited Northflank's secret store: every provider-level
credential below is rotated at its provider, staged in the git-ignored
`k8s/secrets.env`, and applied to the cluster as the `checktick-secrets`
Secret. Proven, not just applied: the post-rotation rollout was healthz-gated
(so the rotated `DATABASE_URL` and Vault AppRole pair demonstrably work end
to end), and a live Microsoft Graph token fetch verified the rotated email
credentials.

| Credential | Action | Status |
| :--- | :--- | :--- |
| Civo DB password | Generated at instance creation | ✅ rotated + proven (healthz-gated rollout) |
| Vault AppRole `role_id` / `secret_id` (staging POC Vault) | New AppRole per [`vault/setup_vault.py`](../vault/) | ✅ rotated + proven; **superseded at cutover** — see below |
| OIDC client secrets (Google, Azure) | Rotate in provider consoles | ✅ rotated |
| `LLM_API_KEY` | Rotate at the APIM | ✅ rotated |
| `EXTERNAL_DATASET_API_KEY` | Rotate at RCPCH | ✅ rotated |
| `TRUD_API_KEY` | Rotate at TRUD | ✅ rotated (SNOMED CronJob only) |
| `EMAIL_HOST_PASSWORD` | Rotate at SMTP provider | ✅ rotated + proven (live Graph token fetch) |
| `HCAPTCHA_SECRET` | Rotate at hCaptcha | ✅ rotated |
| `LOGS_KEY` | New OpenObserve credentials | ✅ rotated |
| GoCardless API/webhook secrets | Rotate in GoCardless dashboard | ✅ rotated |

**Two items are deliberately cutover-time, not pre-rotatable:**

- **Django `SECRET_KEY`** — new at cutover, inside the freeze window.
  Rotating early would invalidate live production sessions and password-reset
  links; with writes frozen at T+0 it is free. Do NOT pre-stage it in
  `secrets.env` — swap the value in the Secret during the window.
- **Vault AppRole credentials on the MIGRATED Vault** — the staging AppRole
  belongs to the throwaway POC Vault, whose storage directory is REPLACED at
  T+2 by the Northflank copy. The migrated Vault therefore carries
  Northflank's AppRole (and its policy, which lacks the
  `secret/data/users/*` stanza — Phase 0 ledger finding). After the copy,
  one root ceremony on the migrated Vault covers everything: mint a fresh
  `secret_id` (new `role_id` comes with the copied role), apply the fixed
  `checktick-app` policy, revoke the temp root — then update `VAULT_*` in
  `checktick-secrets` and re-run `k8s/smoke-test.py` (step 17 gates the
  policy). Alternatively apply the stanza on the Northflank Vault pre-copy
  so it travels with the storage (Phase 3 checklist item) and only the
  `secret_id` mint remains for the window.

Vault unseal shares and the custodian component are **not** rotated by this
move — custody is unchanged (they never transited Northflank). A platform key
rotation is a separate, deliberate ceremony per [Vault](vault/) "Platform Key
Rotation".

## Phase 3 — Pre-cutover (T−7 days → T−1 day)

- [ ] Manifests final; ingress + TLS certificate issued and verified on a
      scratch hostname.
- [ ] **Rehearsal 1 — Vault:** copy the Northflank Vault storage directory →
      restore into a scratch Civo PVC → start Vault → unseal with real shares →
      `vault status` unsealed → issue a scratch AppRole → point a scratch web
      instance with a restored DB copy at it → decrypt one real survey
      (in scratch, privately). Destroy the scratch afterwards. If this fails,
      the cutover will fail — stop here and investigate.
- [ ] **Rehearsal 2 — database:** full `pg_dump` → `pg_restore` into a scratch
      Civo DB; record duration; `python manage.py migrate --check` reports no
      pending migrations; row counts match source.
- [ ] Media pre-sync (bulk `rsync`/`rclone` into the PVC).
- [ ] SNOMED rebuilt on the production PVC; `healthz` reports snomed ok.
- [ ] **Apply the fixed `checktick-app` policy to the production Vault**
      (Phase 0 ledger finding): the migration copies Vault storage, so the
      moved Vault keeps the old policy and recovery-dashboard approvals
      (`users/<uid>/surveys/<sid>/recovery-kek`) stay `permission denied`.
      Root ceremony on the Northflank Vault (or immediately post-move):
      `vault operator generate-root` → `vault policy write checktick-app`
      with the fixed `vault/setup_vault.py` HCL → revoke the temp root →
      re-run `k8s/smoke-test.py` against it (step 17 green). Fresh Vaults
      initialised from the fixed script get the stanza automatically.
- [ ] Lower DNS TTL to 60s at T−24h.
- [ ] Deploy freeze on Northflank from T−24h; announce the window to users
      (email + in-app banner).
- [ ] Fill Appendix B timings; announce window = longest rehearsal + 50%.

## Phase 4 — Cutover window

All times relative to window start (T+0). Verify by counts only — never paste
row contents into terminals or tickets.

1. **T+0 — freeze.** Announce; take a Northflank platform backup/snapshot if
   offered. Scale the Northflank web service to 0 (writes frozen).
2. **T+2 — Vault.** Stop the Northflank Vault. Archive and transfer the
   storage directory encrypted, verify checksum:

   ```bash
   # Northflank side (Vault stopped)
   tar czf vault-storage.tar.gz -C /vault file
   sha256sum vault-storage.tar.gz   # compare after transfer
   # transfer via encrypted channel, then securely delete the source tarball
   ```

3. **T+5 — restore Vault on Civo.** Pre-create the `data-vault-0` PVC, extract
   the archive into it, apply `k8s/vault.yaml`, unseal with 3 of 4 shares,
   confirm `vault status` shows `initialized: true, sealed: false`, then —
   ONE root ceremony on the migrated Vault (`vault operator generate-root`,
   revoke after): mint the new production AppRole `secret_id`, apply the fixed
   `checktick-app` policy **if the `secret/data/users/*` stanza was not
   applied on the Northflank Vault pre-copy** (Phase 3 checklist item), and
   update `VAULT_*` in the `checktick-secrets` Secret. Re-run
   `k8s/smoke-test.py` against it — step 17 gates the policy. Delete the
   tarball.
4. **T+10 — database.** Final dump, transfer, restore:

   ```bash
   kubectl run pgmigrate --rm -it --image=postgres:17-alpine -- bash
   # 17's pg_dump is the correct tool to dump a 16 source (dump with the
   # newer version's binary — never the reverse)
   pg_dump "$NORTHFLANK_DB_URL" -Fc -Z1 --no-owner --no-privileges \
     -f /tmp/checktick.dump
   pg_restore --jobs 4 --clean --if-exists --no-owner --no-privileges \
     -d "$CIVO_DB_URL" /tmp/checktick.dump
   ```

5. **T+10+Δ — verify counts.** Compare row counts per key table
   (`AuditLog`, surveys, survey responses, users) between source and target
   (counts only). Run `migrate --check` — must report no pending migrations.
6. **T+15 — media delta sync** (seconds; volume is small).
7. **T+15 — pre-deploy Job** (`k8s/migrate-job.yaml`; migrations should be a
   no-op, syncs are idempotent).
8. **T+20 — deploy web.** Update `SECRET_KEY` in the `checktick-secrets`
   Secret (new value per Phase 2 — live sessions/reset links invalidate,
   free inside the freeze). `kubectl apply -k k8s/` (excluding CronJobs until
   smoke passes), then `kubectl rollout status deployment/checktick-web`.
   (Routine releases after cutover can instead be dispatched from the
   *Deploy (Civo)* GitHub workflow, which runs these steps with automatic
   rollback — see `k8s/README.md`.)
9. **T+25 — smoke gate. ALL must pass before DNS:**
   - [ ] `/healthz` → `status: ok` (db, vault, snomed)
   - [ ] Log in with a known test account
   - [ ] Create a test survey, submit a response, view/decrypt it — the
         round-trip proves the moved Vault still unwraps the moved data
   - [ ] `/api/health` ok; a hashed static asset loads (`styles.*.css`)
   - [ ] `AuditLog` count ≥ pre-migration count
10. **T+30 — DNS flip** to the Civo ingress. Apply the CronJobs.
11. **T+30 → T+90 — monitor:** `/healthz`, 5xx rate, log counts, and the first
    runs of the daily CronJobs at their next schedule.

## Phase 5 — Rollback posture

- Northflank stays stopped and intact for a fixed **48-hour** rollback window.
- Rollback = DNS back to Northflank + start web. It forfeits any writes made
  on Civo after the flip — so rollback is for blocking defects that cannot be
  hot-fixed forward (forward-fixing via rolling update is fast and safe).
- Never roll back a single component. Vault and PostgreSQL move together or
  not at all.

## Phase 6 — Decommission and close-out

- [ ] Export Northflank operational logs if retention requires continuity,
      then delete all Northflank project data and close the account.
- [ ] Confirm every credential in the Phase 2 table was rotated.
- [ ] Swap the deploy trigger: replace the "Trigger Northflank deployment"
      step in `.github/workflows/docker-publish.yml` with a call to the
      *Deploy (Civo)* workflow. Keep the Northflank webhook in place until
      the cutover window closes — it is the live production path until
      then.
- [ ] Documentation sweep — replace Northflank-specific content:
      - `docs/vault.md` — "Option 1: Northflank (Recommended for Production)"
      - `docs/self-hosting-scheduled-tasks.md` — "Northflank (Recommended)"
        platform section and the L89 reference
      - `docs/versioning-and-deployment.md` — steps 4–5 (Northflank webhook
        and pre-deploy job flow)
      - `docs/infrastructure-logging.md` — "Northflank captures stdout"
      - `checktick_app/settings.py` — L849 comment; `checktick_app/core/views.py`
        — `healthz` docstring
      - `AGENTS.md` — versioning section's Northflank webhook reference
      - Replace with generic "managed platform" language plus a Civo/Kubernetes
        section; keep Docker Compose as the default self-hosting path.
- [ ] Record the change in
      [`docs/compliance/infrastructure-technical-change-log/`](compliance/infrastructure-technical-change-log/)
      including the incident rationale.
- [ ] Update the DPIA / processor record: Civo DPA, sub-processors, region.
- [ ] Post-cutover hardening backlog (separate changes, after stability):
      TLS on the in-cluster Vault endpoint (cert-manager) +
      `VAULT_TLS_VERIFY=true`; k3s Secrets encryption-at-rest on Civo (verify
      feasibility); Velero/PVC backups; staging namespace; alerting on
      `/healthz`; OpenObserve + collector DaemonSet; migrate CNPG backups from
      in-tree Barman to the Barman Cloud Plugin before any operator upgrade
      past 1.30 (in-tree support is removed in 1.31); pin Vault's container to
      a non-root user (`runAsUser: 100` — the image defaults to root, found
      during POC debugging).

## Appendix A — Command reference

```bash
# PostgreSQL 16 -> 17: use the TARGET version's binaries for both steps
pg_dump "$SRC" -Fc -Z1 --no-owner --no-privileges -f checktick.dump
pg_restore --jobs 4 --clean --if-exists --no-owner --no-privileges \
  -d "$DST" checktick.dump

# Count verification (counts only — never dump row contents)
psql "$URL" -tc "SELECT COUNT(*) FROM core_auditlog;"
psql "$URL" -tc "SELECT COUNT(*) FROM auth_user;"

# Vault storage copy (source Vault STOPPED — a sealed-but-running Vault
# may still write; stopped is the only consistent state)
tar czf vault-storage.tar.gz -C /vault file
# target: extract into the data-vault-0 PVC before starting the StatefulSet

# Media pre-sync via helper pod mounting the checktick-media PVC
kubectl run mediasync --rm -it --image=alpine \
  --overrides='{"spec":{"volumes":[{"name":"m","persistentVolumeClaim":{"claimName":"checktick-media"}}],"containers":[{"name":"mediasync","image":"alpine","command":["sh"],"stdin":true,"volumeMounts":[{"name":"m","mountPath":"/media"}]}]}}' -- sh
# then rsync/rclone into /media
```

## Appendix B — Timing rehearsal template

| Step | Rehearsal duration | Notes |
| :--- | :--- | :--- |
| Vault storage copy + transfer + unseal | _tbd_ | |
| Final `pg_dump` | _tbd_ | scales with DB size |
| Transfer dump | _tbd_ | |
| `pg_restore` | _tbd_ | `--jobs 4` |
| Counts verification | _tbd_ | |
| Media delta sync | _tbd_ | |
| Pre-deploy Job | _tbd_ | |
| Rollout + smoke gate | _tbd_ | |
| **Announced window (total + 50%)** | _tbd_ | |

### POC measurements (2026-11-01, tear-down → re-apply test)

The rows above are filled by the Phase 3 rehearsals (they measure the
cutover's dump/restore path). These measure the POC's re-apply mechanics —
evidence that a from-scratch rebuild is fast, and timings for the parts of
the cutover that reuse them:

| Step | Measured | Notes |
| :--- | :--- | :--- |
| `kubectl delete -k k8s/` (namespace gone) | 5m20s | CNPG decommissioning dominates; plan the cutover rollback/DNS around this |
| CNPG bootstrap → 2 ready instances | ~2m15s | primary ready first (~1m), replica joins after |
| Pre-deploy Job (migrate + syncs) | 45–76s | against an empty database |
| Vault StatefulSet + PVC up | ~2m40s | fresh PVC, `civo-volume` |
| Full fresh ceremony (init → unseal → `setup_vault.py` → patch creds) | ~1m | throwaway POC path; production is storage-copy + unseal only |
| SNOMED import (download + seed) | 3m24s | 1.9 GiB from the object store + `seed_snomed_datasets --force` |
| Ingress apply → Let's Encrypt cert `READY True` | ~3m30s | cert re-issued from scratch |
| Web rollout per replica (readiness-gated) | ~1m | `maxUnavailable: 0` |
| `smoke-test.py` 19 steps | ~40s | run inside a live web pod |
| Web pods restart after SNOMED import | required | pod-local emptyDir copy happens at init only

## Appendix C — Scheduled tasks (CronJob equivalents)

| CronJob | Command | Schedule (UTC) |
| :--- | :--- | :--- |
| process-data-governance | `process_data_governance` | daily 02:00 |
| cleanup-survey-progress | `cleanup_survey_progress` | daily 02:10 |
| sync-external-datasets | `sync_external_datasets` | daily 02:20 |
| sync-global-question-group-templates | `sync_global_question_group_templates` | daily 02:30 |
| prune-unconfirmed-users | `prune_unconfirmed_users` | daily 02:40 |
| process-expired-subscriptions | `process_expired_subscriptions` | daily 03:00 |
| process-expiring-subscriptions | `process_expiring_subscriptions` | daily 03:05 |
| process-promotion-lifecycle | `process_promotion_lifecycle` | daily 03:10 |
| process-dsr-deadlines | `process_dsr_deadlines` | daily 03:15 |
| process-diary-reminders | `process_diary_reminders` | daily 03:20 |
| sync-nhs-dd-datasets | `sync_nhs_dd_datasets` | Sunday 04:00 |
| process-recovery-time-delays | `process_recovery_time_delays` | every 5 min |
| import-snomed-db | object-store download + `seed_snomed_datasets` | weekly Tue 14:00 (built by CI: `build-snomed-db.yml`) |

The billing commands are no-ops when `SELF_HOSTED=True`; the hosted service
runs in SaaS mode, so all CronJobs stay enabled. See
[Scheduled Tasks](self-hosting-scheduled-tasks/) for the authoritative list
and semantics.
