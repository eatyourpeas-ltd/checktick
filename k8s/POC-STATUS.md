# POC Status — Civo Migration (session handoff)

> **SUPERSEDED (2026-11-04):** the durable operational knowledge in this log now
> lives in [`docs/civo-kubernetes-operations.md`](../docs/civo-kubernetes-operations.md).
> This log and the migration runbook are retained only until Phase 6 close-out
> (~2026-11-05 22:46 UTC) for the rollback procedure and the close-out checklist,
> then removed. The permanent historical record of the migration is
> `docs/compliance/infrastructure-technical-change-log.md`.

**This cluster is now PRODUCTION** (`https://checktick.uk`, cutover complete
2026-11-03 — see session 9). The sessions below are the build-up history:
Phases 0–3 (provisioning, POC, credential rotation, rehearsals) and the
session-8 outage fix. Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — Phase 0 findings ledger
+ Phase 4 cutover record + Phase 6 close-out backlog) and `k8s/README.md`.
Current release: **0.24.2** (pinned in the manifests and live).

Last updated: 2026-11-04 (end of session 11 — CVE-2026-98432 patched, all nodes re-imaged).

## Environment

- Civo Kubernetes `checktick` cluster, LON1, 3 × medium nodes (2 vCPU/4 GB),
  Kubernetes 1.36.0 (node image: Alpine v3.23 / kernel 6.18.60-0-lts since
  session 11)
- Local kubectl via `~/.kube/civo-checktick.yaml` (exported in `~/.zshrc`)
- CNPG operator v1.30.1; cert-manager installed; Longhorn v1.13.0 installed
- Object store: `checktick-backups` (objectstore.lon1.civo.com), credential
  "backups" attached
- Local (git-ignored) files that carry the environment:
  `k8s/secrets.env`, `k8s/config.env`, `k8s/ingress.local.yaml`,
  `k8s/scratch-*.yaml`, and the DB password in a password manager (also in
  `checktick-db-creds`)
- **All credentials were rotated after the Northflank compromise**; the
  rotated `secrets.env` + `config.env` are pushed to the cluster (see below).

## What is live and verified

- Vault: single node, **migrated PRODUCTION storage** (copied from Northflank
  2026-11-03, NOT re-initialised — safety rule 1), unsealed with the existing
  production 3-of-4 Shamir shares, fixed `checktick-app` policy applied,
  fresh AppRole in `checktick-secrets`, temp root revoked. `vault-0` 1/1.
  Manifest fixes (all POC findings, commented in `vault.yaml`): `fsGroup`,
  `disable_mlock`, direct `command:` invocation. **No scheduled backup yet
  (see next steps — Raft migration is the plan).**
- PostgreSQL 17 (CNPG): 2 instances healthy. WAL archiving to
  `s3://checktick-backups/db` (SigV4 `region` SecretKeySelector + S3 checksum
  env vars required — see Cluster spec.env): **silently broken on the
  session-5 rebuild, root-caused and fixed in session 8** (stale-WAL
  contamination tripped the first-archive check; see session 8), now
  re-verified end to end. Nightly base backup 02:00 UTC — first restorable
  chain from 2026-11-04.
- Migrate job (`checktick-predeploy`): **passed** — full credential chain
  Django → Secret → service → CNPG verified; migrations and syncs complete.
- Web Deployment: 2 replicas, Longhorn RWX PVCs bound (media + SNOMED share),
  running `ghcr.io/eatyourpeas-ltd/checktick:0.24.2` — pinned via Deploy
  (Civo) in session 8 (was `latest`; live == manifest now, so
  `kubectl apply -k k8s/` no longer resets the image).
- Rotated credentials pushed: `checktick-secrets` + `checktick-config-local`
  re-applied from the cycled files; rollout was healthz-gated (so the rotated
  `DATABASE_URL` + Vault AppRole are proven working) and a live Graph token
  fetch verified the email creds (the signup-time 401 is fixed).
- `/healthz`: **full `status: ok`** — `db: ok`, `vault: ok`, `snomed: ok`
  (SNOMED verified end to end this session), via pod localhost, Service DNS,
  and public HTTPS.
- Zero-downtime proof: **PASSED** — the `zdt-test` curl loop pod has been
  running through **three** full `rollout restart`s with zero FAILs.
- Ingress + TLS: Traefik routes BOTH `checktick.uk` (production, Let's Encrypt
  `checktick-uk-tls` READY) and `staging.checktick.uk` (window leftover —
  remove after the rollback window closes); public HTTPS serving 200 on both.
- DB ingress airgap (session 9): `k8s/postgres-networkpolicy.yaml` — 5432
  only from web pods / own instance pods / the CNPG operator; verified
  positive (healthz, streaming, operator clean) and negative (unlabelled pod
  times out). Vault airgap unchanged (`vault-airgap`).
- CronJobs: all 13 applied (incl. `import-snomed-db` — verified end to end
  via `kubectl create job --from=cronjob/import-snomed-db snomed-import -n
  checktick`);
  `process-recovery-time-delays` verified running to completion.

## Session 3: the "too many redirects" on staging

- **Root cause is app-level, not infrastructure** — reproduced mechanically
  in the live pod (Django test client, throwaway user in the same state →
  `RedirectCycleError`): `Require2FAMiddleware` and the
  `email_confirmed_required` decorator cycle an authenticated password user
  with unconfirmed email between `/home` and `/2fa/setup/` forever. Full
  mechanism + production impact in the runbook Phase 0 ledger.
- Staging hit it because Google signup auto-logs in with
  `email_confirmed=False` while the confirmation email 401'd (stale creds).
  Production runs the same released code; it just doesn't have users in
  that state.
- **Fix on this branch (ships in 0.24.0):** middleware exempt list corrected
  (real `/2fa/` route, confirmation + resend recovery routes, `/home`),
  `is_password_user` empty-password fix, regression tests in
  `checktick_app/core/tests/test_2fa_middleware.py` (71 tests green incl.
  all email-confirmation / anti-bot-prune suites — gating behaviour
  unchanged).
- Staging accounts: both test users still have `email_confirmed=False`
  (their confirmation emails never delivered). Resend AFTER the 0.24.0
  roll-out so the link works even while logged in.

## Session 4: staging live, CI deploy green, SNOMED end to end

- Staging is serving real HTTPS traffic on `staging.checktick.uk`; the
  redirect-loop fix shipped (0.24.0 → 0.24.1 merged to `main`) and the
  Deploy (Civo) workflow runs green.
- **SNOMED pipeline verified end to end:** "Build SNOMED DB" workflow →
  `s3://checktick-backups/snomed` → `kubectl create job
  --from=cronjob/import-snomed-db snomed-import` (1.9 GB download + atomic
  rename onto the RWX PVC + `seed_snomed_datasets --force`) — release
  2026-10-21, 19 dataset descriptors seeded. NOTE the in-cluster import
  job is NOT automatic after the CI build — the CronJob schedule is
  Tuesday 14:00 UTC; healthz stays `snomed: unavailable` until it runs.
- **SNOMED WAL finding (full entry in the runbook Phase 0 ledger):** `sct`
  builds `snomed.db` in WAL mode, so every `mode=ro` reader (healthz,
  `snomed_resolver`, `seed_snomed_datasets`) needs to create a `-shm`
  file — fine on the seed Job's read-write PVC mount, impossible on the
  web container's `readOnly: true` emptyDir mount
  (`SQLITE_CANTOPEN`, healthz `snomed: error`). **Fix in `k8s/web.yaml`:**
  the `snomed-copy` init container runs `PRAGMA journal_mode=DELETE` on
  its pod-local copy after the `cp` (the emptyDir is read-write there; the
  RWX share is never written). Applied to the live Deployment via a
  name-keyed strategic patch so the live `ALLOWED_HOSTS` env and image
  were untouched. Verified: init logs print `journal_mode: delete`, both
  pods `snomed: ok`, public `/healthz` fully `ok`.
- Web pods must be restarted (rollout restart) after any import run —
  the emptyDir copy only happens in the init container at pod boot.
- **Phase 1 round-trip smoke: PASSED 19/19** — `k8s/smoke-test.py`, run
  inside a live web pod (`kubectl exec ... python /tmp/smoke-test.py`)
  against the real staging DB/Vault/snomed.db, all through the REAL views:
  login view + TOTP 2FA verify, encrypted survey create (X25519 keypair,
  dual-path wraps), builder question create incl. SNOMED dataset binding
  (POST field is `prefilled_dataset`), snomed_resolver on the pod-local
  copy (3,743 options, release 2026-10-21), anonymous submission stored
  as an ECIES blob with no plaintext, password unlock, export CSV decrypt
  (marker + SNOMED preferred term), recovery-phrase unlock, Vault KV
  escrow write→read→delete via AppRole, AuditLog writes. Public gate:
  `/healthz` ok, `/api/health` ok, hashed `styles.*.css` 200.
  Throwaway user/survey deleted afterward (AuditLog actor is SET_NULL).
- **Vault AppRole policy gap found by the smoke (runbook Phase 0 ledger):
  the `users/<uid>/surveys/<sid>/recovery-kek` path used by the recovery
  dashboard is NOT in the `checktick-app` policy — approvals would fail
  with `permission denied`. Pre-existing (same `setup_vault.py` on
  Northflank), not Civo-specific. **Fixed and APPLIED:** the stanza is in
  `vault/setup_vault.py` (this branch), and the staging Vault got it via the
  root ceremony (`vault operator generate-root` with 3-of-4 shares →
  `vault policy write checktick-app` → revoke temp root). Smoke step 17
  exercises the real `users/...` escrow path and is GREEN — 19/19 with the
  recovery path included. The migration copies Vault storage (no re-init),
  so the PRODUCTION Vault still needs the same apply before/after cutover
  (runbook Phase 3 checklist); fresh Vaults get it automatically.

## Session 5: Phase 1 exit criteria — idempotency + tear-down test

- **Idempotency check: PASSED.** Two consecutive `kubectl apply -k k8s/` —
  Deployment spec converged, generation stable, no new pods, `vault-0`
  uptime untouched. `vault`/PDB/NetworkPolicy print `configured` on every
  apply but a field-by-field compare shows zero spec differences: the
  recurring `configured` is empty-patch metadata churn (generation tick),
  not drift. `zdt-test` pod deleted after recording its final tally:
  **0 FAILs across five rollouts**.
- **Tear-down → re-apply test: PASSED** (`kubectl delete -k k8s/`, namespace
  gone in ~5m20s) and re-applied from scratch. Sequencing findings on the
  way (full entries in the runbook Phase 0 ledger):
  - **Dual-default StorageClass bug (the big one):** `civo-volume` AND
    `longhorn` were both annotated default, so the CNPG data PVCs and the
    Vault PVC silently landed on Longhorn. Longhorn's size×3 reservation
    per node exhausted the ~35 GiB free per node → the RWX media/snomed
    volumes failed replica scheduling (`insufficient storage`, volumes
    `detached/faulted`) → web pods hung `Init:0/2` and the SNOMED import job
    sat unscheduled for 20+ min looking like a slow download (zero
    init-container logs = volume-attach failure, not network). Fix: removed
    the default annotation from `longhorn` (single default `civo-volume`,
    matching the manifest comments), deleted + recreated the CNPG cluster
    and Vault — RWX volumes attached immediately, import ran in its normal
    **3m24s**.
  - **Apply order is load-bearing:** predeploy hit
    `CreateContainerConfigError` when `checktick-config` didn't exist yet,
    and the import job Pending on a not-yet-created PVC. README order
    (config → secrets → workloads) must be followed exactly.
  - **The out-of-band objects had to be exported first:**
    `checktick-secrets` is NOT rebuildable from `k8s/secrets.env` — it alone
    carries `OIDC_OP_TENANT_ID_AZURE` (`settings.py` reads it without a
    default → app crashes at import). `SELF_HOSTED` in the live Secret is
    the string `"False"` (leftover quoting artefact) — django-environ
    parses it to False, i.e. correct SaaS mode for the hosted service.
    Exports live in git-ignored `k8s/scratch-export-*.json`.
- **Fresh Vault ceremony on the rebuilt Vault** (throwaway POC init —
  production stays storage-copy): `vault operator init -key-shares=4
  -key-threshold=3`, unseal ×3, `vault/setup_vault.py` via a temp pod
  labelled `app=checktick-web` (airgap), fresh AppRole patched into
  `checktick-secrets`, throwaway root token revoked. Tooling:
  `k8s/scratch-vault-ceremony.sh` + `k8s/scratch-revoke-root.sh` (git-
  ignored; note Vault 1.21.1 emits `unseal_keys_b64`, and the CNI needs
  ~15 s before a fresh pod can reach `vault:8200` — the script retries).
- **Rebuild verified end to end:** predeploy Complete, SNOMED import
  Complete (3m24s), cert `READY True`, `/healthz` fully `ok` via pod /
  Service DNS / public HTTPS, and **`smoke-test.py` re-run 19/19 green**
  against the rebuilt environment (incl. step 17, the `users/*`
  recovery-escrow path).
- **Phase 2 re-verified post-rebuild:** the restored `checktick-secrets`
  carries the rotated provider credentials and the fresh AppRole pair;
  healthz-gated rollouts and the smoke prove them working.

## Session 6: real email delivery verified, Azure SSO fixed

- **Real email delivery verified end to end:** a fresh account was
  created on staging via the normal signup flow and the confirmation
  email was received and clicked. Next-steps item 1 is done — the only
  leftover is the two older test accounts still at `email_confirmed=False`
  if you want them usable.
- **Azure SSO was broken — fixed.** Symptom: `AADSTS900023: Specified
  tenant identifier '""'`. Root cause: the live `checktick-secrets`
  carried `OIDC_OP_TENANT_ID_AZURE` as the literal two-character string
  `""` (quote artefact from the out-of-band restore, same class as the
  `SELF_HOSTED: "False"` value; the key was missing from
  `k8s/secrets.env` entirely). Truthy string → settings.py's
  `or "common"` fallback never fired → authorize URL built as
  `login.microsoftonline.com/""/...`. Google SSO was unaffected
  (no tenant in its URLs).
- **Fix applied (final value: `common`):** live Secret patched and the
  key added unquoted to `k8s/config.env` as
  `OIDC_OP_TENANT_ID_AZURE=common`; `checktick-config-local` re-applied,
  healthz-gated rollout restarted, `/healthz` fully ok. Verified from
  inside a pod: the `common` authorize endpoint returns **200
  (Microsoft sign-in page)** with the staging redirect URI. NOT the org
  tenant GUID — see the AADSTS90123 note below. The scratch export was
  re-exported so future teardown/restore carries the fixed value.
  Full ledger entry in the runbook Phase 0 findings.
  **Cutover note:** production's effective value must stay `common` when
  its env moves — do not pin the org GUID.
- **OIDC redirect resolution (corrected after the retest):**
  mozilla-django-oidc derives the redirect URI from the request host
  (`absolutify(request, ...)` in BOTH the authorize and token steps), so
  staging sends `https://staging.checktick.uk/oidc/callback/` and the SSO
  loop completes on staging for both providers. The hardcoded prod
  `settings.OIDC_REDIRECT_URI` is unused by this version of the library.
  Both app registrations carry the staging URI — Google completes end to
  end, and the Azure flow gets past redirect validation.
- **AADSTS90123 explained and resolved:** an initial fix pinned the
  tenant to the `5630eab2` GUID — the user reached the Microsoft sign-in
  page, but Azure then denied token issuance ("identity or claim
  issuance provider denied the request") because the test account is a
  **personal M365 account**, and production accepts personal accounts —
  i.e. production's effective tenant is `common`, and a tenant-scoped
  authorize endpoint refuses personal accounts at claim issuance. Value
  switched to `common` (which also accepts organisational accounts from
  any tenant — the NHSmail model), rolled out, authorize endpoint
  verified 200. Pending: user retest with the personal account to
  confirm the full loop on staging.
- **Quote-artefact audit:** all six keys that exist in the live Secret
  but not in `k8s/secrets.env` are quote-wrapped (`OIDC_OP_TENANT_ID_AZURE`,
  `SELF_HOSTED`, 4 × `HOSTING_*`). `SELF_HOSTED` only works because
  django-environ's bool parser strips quotes. The `HOSTING_*` values are
  stale Northflank API credentials — recommend dropping them at cutover
  rather than migrating.

## Session 7: Phase 3 rehearsal drills — tooling built + mechanically proven

Both runbook Phase 3 rehearsal drills now have git-ignored drill tooling
under `k8s/scratch-drill-*` (the `.gitignore` rule was broadened to
`k8s/scratch-*` — the old per-extension list kept missing new suffixes):

- **Rehearsal 2 (database):** `scratch-drill-db.yaml` (1-instance scratch
  CNPG cluster; deliberately NO backups — a production copy must never hit
  the object store; no bootstrap secret — CNPG publishes the URI in the
  `scratch-drill-db-app` Secret) + `scratch-drill-db-run.sh`: timed
  `pg_dump`/`pg_restore` with the exact cutover T+10 commands, exact
  per-table count diff (counts only), `migrate --check` Job, and it prints
  the Appendix B timing table. Input: `k8s/scratch-nf-db.env` with the
  production `NORTHFLANK_DB_URL` (script prints the template).
- **Rehearsal 1 (Vault):** `scratch-drill-vault.yaml` (air-gapped to
  `app=scratch-drill-web` only), `scratch-drill-vault-restore.sh` (PVC
  pre-create, checksum verify, extraction with the CRITICAL `file/`-prefix
  layout normalisation), `scratch-drill-vault-ceremony.sh` (generate-root →
  policy check/write → AppRole mint → revoke; run by the OPERATOR in their
  own terminal — real shares/tokens never transit an agent session),
  `scratch-drill-web.yaml` (restored DB + migrated Vault, no ingress, locmem
  email), `scratch-drill-decrypt.py/.sh` (decrypt proof — booleans only),
  `scratch-drill-teardown.sh`.

**Mechanical validation ran green (staging data + throwaway POC Vault
shares — zero production data):**

- DB drill staging→scratch: dump 1s (400 KB compressed) / restore 4s /
  78 tables exact count match / `migrate --check` clean. CNPG 1-instance
  bootstrap: 1m50s.
- Vault drill: staging Vault stopped → tarred (with the Northflank-style
  `file/` prefix) → restarted → unsealed (the exact Northflank-side
  procedure); the restore script rebuilt it in-cluster as
  `Initialized: true, Sealed: true` (storage-copy migration, NOT re-init);
  unsealed with the throwaway shares; generate-root + policy skip/write
  branches + AppRole mint all proven; scratch web `/healthz` fully ok; **smoke
  19/19 including step 15 (export decrypt) and step 17 (`users/*` escrow)
  against the MOVED storage**. Staging left fully healthy
  (`db/vault/snomed: ok`) and the scratch environment torn down cleanly.

Findings are recorded in the runbook Phase 3 ("Rehearsal drill findings") —
the archive-layout one is cutover-critical and is also flagged at Phase 4
T+5. Remaining operational findings: RWO re-attach delay (~4–5 min),
`WaitForFirstConsumer` PVC binding, Vault 1.21.1 CLI specifics
(positional generate-root key, auto-OTP, `vault write -f`), CNPG PVC naming
(`<cluster>-<N>`), `--dry-run=server` for manifest validation.

**Northflank platform access (post-breach) — RESOLVED same day
(2026-11-02): Northflank re-enabled the account-level features in response
to the support request. Verified live with the CLI (`@northflank/cli`
0.15.0) + a fresh API token:

- `exec` (shell/commands): **WORKS** (verified: `vault status` inside the
  vault container; note the CLI runner takes the string as ONE program —
  use `vault status -address=http://127.0.0.1:8200` style flags, or an
  interactive shell session for hidden-prompt commands).
- `download` (file pull): **WORKS** (verified with a probe file).
- `forward` (port-forward): **WORKS** (verified 2026-11-02) after minting a
  new owner-scoped token carrying the Port Forward permission — the
  unseal/ceremony channel is a local tunnel + the LOCAL `vault` binary,
  so shares never enter the platform. The `vault` binary (1.21.4, direct
  download from releases.hashicorp.com — checksum-verified; the hashicorp
  brew tap was unwritable from the dev account) is installed at
  /usr/local/bin/vault. The tunnel exposes Vault's 8200 on a loopback port
  (`--skipHostnames`).
- Stop/start/scale services (patch service): works (deprecated scale
  endpoint → use `northflank patch service combined`).
- Volumes: `vault-data` (10 GiB, RWO) mounts at **`/vault/file`** in the
  vault container — the volume IS the storage directory, so the runbook
  tar command (`-C /vault file`) produces the `file/`-prefixed layout the
  restore script normalises. Volume backup/restore exists but volume
  backups have NO download endpoint — moot now.

Consequences and confirmed state:
- **Exec cannot reach a STOPPED service** — the tar must run in the
  one-off manual job `vault-storage-tar` (created 2026-11-02,
  `k8s/scratch-nf-tar-job.json`, does NOT run until triggered): stop
  Vault → `attach volume` vault-data to the job at `/vault/file` → run →
  sha256 in job logs + `TARDONE` marker → `northflank download job file` →
  detach + delete job → start Vault → unseal.
- **Version finding (important):** the live production Vault reports
  **1.21.4**, not the 1.21.1 the manifests assumed — a storage-copy into
  an OLDER Vault is not a supported direction. `k8s/vault.yaml` and
  `k8s/scratch-drill-vault.yaml` now pin **1.21.4**; the staging vault-0
  was rolled to 1.21.4 and re-unsealed (live == manifest == source);
  `k8s/scratch-unseal-staging.sh` added for the post-roll ceremony.
- Share hygiene: prefer forward+local for share-bearing commands if the
  token permission becomes grantable; else exec interactive shell
  (hidden prompts). Post-cutover `vault operator rekey` on the migrated
  Vault is recommended follow-through (original shares were minted on
  Northflank pre-breach).
- Unblocked meanwhile: the drill survey can be created in the production
  UI now (no platform access needed).

**Cutover-day tooling (all git-ignored, this machine only):**
`scratch-cutover-vault-copy.sh` (the full T+2 sequence, ready to run —
pause/detach/attach/run/download/abort with checksum verification, plus
the rollback reference in its footer), `scratch-drill-db-run.sh` (T+10
dump/restore; reads `scratch-nf-db.env`), `scratch-drill-vault-restore.sh`
(T+5 restore — usable for the cutover with names adjusted, or follow
runbook Phase 4 T+5 which now carries the layout normalisation warning),
`scratch-drill-vault-ceremony.sh` (T+5 root ceremony),
`scratch-unseal-staging.sh`, and the Northflank `vault-storage-tar` job
(create from `scratch-nf-tar-job.json` if ever deleted). The PUBLIC
command reference (placeholders, no secrets) is in the runbook
Appendix A — a fresh clone can execute the whole migration from it.

**What the REAL drills still need (operator inputs, in order):**

1. ~~Production DB drill~~ **DONE (2026-11-02): PASS** against the live
   Northflank DB (external endpoint — see runbook findings: external access
   enabled, port 28746, `NORTHFLANK_DB_IP` hostAliases pin against DNS
   negative-cache flake). Measured: dump 2s (1.2 MB compressed, source PG
   16.14) / restore 8s (4 expected Northflank monitoring-extension errors
   whitelisted) / **78 tables exact count match** / `migrate --check` clean
   (prod schema current on 0.24.2 — cutover migrate is a no-op). The
   restored copy stays in `scratch-drill-db` for the Vault drill's decrypt
   proof. Timings recorded in runbook Appendix B.
2. ~~Root ceremony on the PRODUCTION Vault pre-copy~~ **DECIDED AGAINST
   (2026-11-02): defer to post-move on Civo.** The ceremony only ADDS the
   `users/*` escrow capability (no working flow changes), but it would
   newly enable the recovery-escrow feature on production — and skipping
   it keeps production untouched until cutover. Bonus: the drill copy
   then carries the STALE policy, so the drill rehearses the exact T+5
   sequence the cutover will run (generate-root → policy write-if-stale →
   AppRole mint → revoke) — the write-if-stale branch is the one already
   validated mechanically. Recovery goes live post-cutover as the intended
   fix.
3. ~~Production Vault storage copy~~ **DONE (2026-11-02):** pause service →
   detach `vault-data` → attach to the `vault-storage-tar` job → run →
   sha256 in job logs → download (checksum verified end to end) → detach →
   re-attach to vault → resume → operator unsealed via forward + local
   `vault` binary. See the runbook's production Vault drill findings for
   the volume-holding stall and the pause/attach semantics.
4. ~~Scratch restore + unseal + ceremony~~ **DONE (2026-11-02):** restore
   script rebuilt the migrated Vault (`Initialized: true, Sealed: true`),
   operator unsealed with the real 3-of-4 shares, ceremony script ran the
   stale-policy variant (the faithful T+5 rehearsal): generate-root →
   policy write-if-stale → AppRole mint → temp root revoked.
5. ~~Drill survey + decrypt proof~~ **DONE (2026-11-02): PASS.** The
   operator's own production survey (Option 2, 3 responses, synthetic
   marker) — decrypt proof green: **3/3 responses decrypted through the
   moved Vault, marker found** (booleans/counts only). The scratch web
   instance passed healthz (db + vault + snomed) against the restored DB
   copy + migrated Vault. Scratch environment destroyed afterwards;
   staging untouched (healthz fully ok).
6. ~~Timings → Appendix B~~ **DONE** — see the runbook's filled rows: DB
   (dump 1–2 s / restore 7–8 s / counts exact / migrate --check clean) and
   Vault (~20 min window incl. a ~10 min preventable stall — abort the tar
   job run before resuming the Vault; clean path ~10–12 min). Recommended
   announced window: **~30 min**, finalise after the media delta sync is
   measured.

**Both Phase 3 rehearsals PASSED against real production data.**

~~Media pre-sync~~ **DONE (2026-11-02):** the whole volume is 29 KB / 1
file (admin brand icon). Tarred from INSIDE the running production web
container via CLI exec (no detach, no outage, no job) → download →
extracted into the Longhorn RWX `checktick-media` PVC via helper pod →
chown 999:999 → verified visible to the live staging pods. Seconds end
to end; timing recorded in runbook Appendix B. Cutover T+15 delta =
same pattern repeated.

**Phase 3 is now COMPLETE except the T−24h operational items** (DNS TTL
to 60s, Northflank deploy freeze, user announcement), which only exist
once a window is booked. Announced window recommendation: **~30 min**
(clean-path vault copy ~10–12 min + DB seconds + media seconds +
pre-deploy ~1 min + rollout/smoke ~3 min + 50% contingency). Book it.

Post-cutover backlog: `vault operator rekey` on the migrated Vault
(shares were minted on Northflank pre-breach); revoke the drill API
token if scoped beyond the migration; media delta at T+15.

## Session 8: WAL-archive contamination outage — fixed, archiving genuinely verified

**What happened (2026-11-03):** staging went down ~20:01 UTC. The primary
(`checktick-db-1`) crash-looped with "no free disk space for WALs" — CNPG's
instance manager refuses to start PostgreSQL on a full WAL volume. The `-rw`
service had no working backend, so both web pods failed their `/healthz`
startup probes and the 5-minute CronJobs errored. A Deploy (Civo) dispatch
(the image pin, below) failed at the pre-deploy step as an early casualty;
the workflow correctly changed nothing (rollback skipped — the image was
never set).

**Root cause (proven, not inferred):** the session-5 tear-down test deleted
the cluster but not the bucket. CNPG runs `barman-cloud-check-wal-archive`
before a fresh cluster's FIRST WAL archive (bootstrap marker file in PGDATA,
default-on) and demands an EMPTY WAL archive. The dead POC cluster's 8 WALs
still sat under `s3://checktick-backups/db/checktick-db/wals/`, so every
archive attempt since the rebuild failed with "Expected empty archive"
(`ContinuousArchiving: False` since 2026-11-01T22:48:17Z — one minute
after bootstrap). Unarchived WAL accumulated at ~one 16MB segment per 5 min
(the `process-recovery-time-delays` schedule) ≈ 4.6 GB/day and filled the
10Gi PVC after ~46 h.

**Diagnosis:** a manual `barman-cloud-wal-archive` from a scratch pod with
the SAME creds/endpoint/env SUCCEEDED — pipeline, credentials, RBAC and the
known region/checksum gotchas were all fine. Reading barman 3.19.1's
`xlog.check_archive_usable` + `cloud_check_wal_archive.py` (from inside the
CNPG image) confirmed the semantics: no `--timeline` argument → any
existing WAL → "Expected empty archive". The error then showed up verbatim
in db-1's startup logs.

**Fix (both halves needed):**

1. **PVC `checktick-db-1` expanded 10 → 20Gi.** Civo's CSI supports
   expansion (`allowVolumeExpansion: true`) but OFFLINE only — it refuses
   in-use volumes. Sequence: scaled the CNPG operator to 0 (stops pod
   recreation; running instances are unaffected — the manager runs
   PostgreSQL independently of the operator), deleted the crash-looping
   pod, let the csi-resizer (sidecar in `civo-csi-controller-0`) expand
   the detached volume, restored the operator. The kubelet finished the
   filesystem resize when the pod re-attached. In that window the operator
   failed over to `checktick-db-2` (new primary, timeline 2) — benign;
   db-1 later rejoined as a healthy replica.
2. **Purged the 9 stale WAL objects** under `db/checktick-db/wals/` (the
   dead cluster's 8, incl. its `.backup` label, plus 1 diagnostic upload
   from this session's testing). The old cluster's base backup
   (`base/20261101T020001/`) was left — the check only scans `wals/`.

**Recovery:** db-1's startup retry then passed the check and — a "former
primary" archives pending WALs BEFORE rejoining, so a stuck check blocks
the whole startup — drained its entire ~640-segment backlog to the
bucket, recycled the segments, and rejoined. Cluster: `Cluster in healthy
state`, 2 instances, `Ready: True`, **`ContinuousArchiving: True`**.
Public `/healthz` fully ok.

**Backup state (runbook-relevant):** the Nov 2 nightly base backup NEVER
uploaded its data — the bucket held only the DEAD original cluster's
`20261101T020001` base. I.e. the rebuilt cluster had NO restorable backup
from Nov 1 22:47 until this fix. The 02:00 UTC run on 2026-11-04 is the
first valid base backup + complete WAL chain.

**Image pin DONE:** Deploy (Civo) re-dispatched with `image-tag: 0.24.2`
after recovery — green end-to-end (pre-deploy job, readiness-gated
rollout, smoke). Live Deployment: `ghcr.io/eatyourpeas-ltd/checktick:0.24.2`.
Next-steps item 2 closed.

**SSO retest DONE (operator, 2026-11-03):** the Microsoft button completes
the full OIDC loop on staging with the personal M365 account. Next-steps
item 3 closed.

**Tooling added:** `k8s/scratch-barman-test.yaml` (git-ignored) — a
throwaway pod manifest that replicates CNPG's barman invocations with the
live backup-creds Secret via `envFrom` (secret values never printed; only
env NAMES were ever displayed). The pod was deleted after use.

**Rules going forward (also recorded in the runbook findings):**

- After ANY rebuild of the DB cluster, re-verify `ContinuousArchiving`
  flips True and a fresh base backup lands — "verified" claims do not
  survive a rebuild.
- When rebuilding into the same barman destination, CLEAN `wals/` first —
  the empty-archive check is correct protection, not an obstacle.
- Civo PVC expansion is offline-only (operator to 0 → delete pod →
  resizer → operator back), and PVCs cannot shrink afterwards.

## Session 9: CUTOVER COMPLETE (2026-11-03, 22:05–22:50 UTC)

**Production is live on Civo.** `https://checktick.uk` → 200, `/healthz`
fully ok, both certs READY, CronJobs resumed, first post-cutover 5-min
cron Complete against production data, DB cluster Ready with
`ContinuousArchiving: True`. Northflank: stopped (NOT deleted) — 48 h
rollback window per runbook Phase 5, from ~22:46 UTC 03/11.

**Timeline (UTC):** 22:05 freeze (NF web paused, 13 Civo CronJobs
suspended — NF scheduled jobs confirmed daily-only, nothing fired) →
22:09 Vault copy (sha256 verified) → 22:13 storage restored
(`Initialized: true, Sealed: true`; 46 POC files wiped, 47 prod files
extracted, `file/` normalisation applied) → operator unsealed 3-of-4 →
ceremony → 22:30 AppRole into `checktick-secrets` (secret-to-secret,
never decoded) + healthz-gated rollout → 22:33 DB: dump 2s / restore 10s /
**78 tables exact** / `migrate --check` clean → 22:41 `SITE_URL` +
new `SECRET_KEY` + `HOSTING_*` dropped + pre-deploy clean + rollout →
22:43 smoke gate 19/19 (incl. step 17 escrow) + public healthz ok →
operator DNS flip → 22:50 `checktick-uk-tls` READY (issued ~2 min after
flip) → CronJobs resumed → 22:53 first cron Complete → tarball securely
deleted from /tmp.

**Tooling bugs found live (both fixed in the cutover variants):**

- `scratch-cutover-vault-copy.sh` step 3: `northflank start job run --output
  json` returns a shape the script's `json.load(...)['data']` didn't match
  (`KeyError: data`). Harmless — the run HAD started; the run id was read
  from `get job logs`'s picker instead. Parse defensively before next use.
- `scratch-cutover-vault-ceremony.sh` step 2: the `grep -q` pipeline under
  `set -o pipefail` misreported the policy write as failed ("policy write
  did not take effect") — the write HAD taken effect (`Success! Uploaded
  policy`). The ceremony aborted BEFORE minting the AppRole and BEFORE
  revoking the temp root. Fixed in `scratch-cutover-vault-resume.sh`
  (captured-output verification, no pipes): verified the policy in place,
  minted the AppRole, revoked the root. **Port that verification pattern
  back into the ceremony script before it is ever reused.**

**ALLOWED_HOSTS gotcha hit as predicted (known state, session 8):** the
T+20 `kubectl apply -f k8s/web.yaml` reset the live ALLOWED_HOSTS patch
→ public staging URL 400s → re-applied the window patch
(`scratch-allowhosts-patch.yaml`, now carrying BOTH hostnames) →
healthz-gated rollout → green. The ALLOWED_HOSTS_EXTRA settings.py fix
remains the proper solution (Phase 6 backlog).

**Post-cutover hardening applied same night (user-approved):**

- `k8s/postgres-networkpolicy.yaml` (in kustomization): DB ingress
  airgap — 5432 only from web pods, own instance pods (streaming), and
  the CNPG operator; verified positive (healthz ok, streaming = 1,
  operator error-free) and negative (unlabelled pod times out).
  Egress deliberately unrestricted (WAL/base backup uploads).
- Dead-POC debris removed from the object store: the ORIGINAL POC
  cluster's base backup (`base/20261101T020001/`, 2 objects) +
  `db/upload-test.txt` (checksum-investigation leftover). `wals/`
  untouched (current cluster's timeline-2 archive, 568 objects).
- Compliance change log updated: cutover entry + timings table + the
  30/10/2026 Northflank incident driver (status page link) + the
  NetworkPolicy entry.

**Backup posture as of cutover:** DB — nightly 02:00 UTC base backup +
continuous WAL to `s3://checktick-backups/db`, 30-day retention,
`ContinuousArchiving: True`; **first fully valid backup chain starts with
the 02:00 run on 2026-11-04 — VERIFY IT LANDS**. Vault — no scheduled
backup yet (tonight's copy was manual; see backlog). Media — none (29 KB
/ 1 regenerable file; Longhorn snapshots would cover it).

## Session 10 (2026-11-04 morning): nightly backup schedule was silently blocked — found + fixed

The user's first backup check post-cutover found the schedule had NOT run.
Root cause was a **compound failure**, not the archiving fix:

1. The Nov 2 02:00 Backup never reached a terminal phase (`walArchivingFailing`
   — it ran while archiving was broken) — data never uploaded.
2. **CNPG's ScheduledBackup refuses to fire while ANY Backup is non-terminal**
   — it logged "The system is already taking a backup for this ScheduledBackup,
   retrying in 60 seconds" every minute **from Nov 2 to Nov 4 09:30** (two
   nightly runs silently skipped).
3. The stuck Backup could never be finalised: its recorded pod IP
   (`10.0.0.80:8000`) died in the session-8 pod churn — the controller's
   status poll times out forever (`Cannot extract Pod status ... i/o timeout`).

**Fix:** deleted the dead Backup resource (safe — its data never uploaded;
CNPG does not delete bucket objects on resource delete). The controller
immediately created the catch-up Backup (named for the missed slot:
`checktick-db-backup-20261103020000`) and it ran to **`completed`** in ~90s:
`base/20261104T093349/` (data.tar.gz 5.9 MB + backup.info) in the bucket,
WAL chain continuous (694 objects, timeline history intact).
**The DB now has its first restorable base backup + PITR.** Next nightly:
2026-11-05 02:00 UTC (the Nov 4 02:00 slot was skipped by the catch-up —
cron semantics, next future occurrence).

Gotchas recorded for next time:

- `kubectl delete backup ...` resolves to **Longhorn's** CRD — use
  `backup.postgresql.cnpg.io` for CNPG.
- **Alerting on Backup phase is now Phase-6 backlog material**: a single
  stuck non-terminal Backup silently blocks the entire nightly schedule.
  `kubectl get backups.postgresql.cnpg.io` phase != `completed` after
  02:10 UTC = investigate.
- The check command for future mornings (this found the problem):
  `kubectl -n checktick get backups.postgresql.cnpg.io` — expect the newest
  row `completed`; `walArchivingFailing` on the newest row = schedule blocked.

### Session 10 addendum (2026-11-04 afternoon): the healthchecks masking + NF job suspension

The user reported "all healthchecks passed overnight" — **those pings were
NORTHFLANK's, not Civo's**. Both job systems were live overnight, pinging the
SAME check UUIDs on healthchecks.io:

- The **Civo 02:00–03:20 batch FAILED** (the db-ingress policy from
  23:11 Nov 3 blocked the job pods; every-5-min recovery also failed from
  23:09 → fixed 09:44 Nov 4). **No Civo pings.**
- The **Northflank jobs fired at their OLD times** (01:00–10:00 UTC daily;
  `suspended=False`, never suspended at cutover) against the frozen NF DB
  and pinged every check UUID → **the dashboard stayed green while the
  live Civo jobs were failing.** Exactly the dual-runner ambiguity — it
  materialised on night one.

**Fix (2026-11-04 ~13:20 UTC): all 11 Northflank cron jobs SUSPENDED**
(verified `suspended=True` on each). From tonight only Civo pings —
unambiguous. CLI gotchas found on the way:

- `northflank patch job -i '{"suspended":true}'` does NOT pause a cron job
  (patches a different/deprecated field; `settings.cron.suspended` is not
  settable via patch — it echoes back unchanged).
- The working command is the **deprecated** `northflank suspend job
  --project census --job <j> -i '{"suspended":true}' --skipValidation`
  (do NOT run it without `-i` — it prompts on a TTY).
- Resuming if ever needed: `northflank resume job ... -i '{"suspended":false}'`.

**Overnight impact assessment (nothing needs manual re-run):**

- Today's diary reminders went out via NORTHFLANK (10:00, frozen DB) —
  Civo's 03:20 run was blocked → users got ONE set, no duplicates today.
  Tomorrow only Civo runs (03:20).
- Failed daily jobs (data-governance, cleanup, sync, prune, expired,
  expiring, promotion, dsr) are all idempotent — **tonight's batch redoes
  the work**; only side effect is a one-day delay on e.g. tier downgrades.
- NF jobs mutated the frozen rollback copy until suspension (data-gov
  soft-deletes, prune, downgrades) — rollback fidelity degraded but the
  window closes 2026-11-05 22:46 UTC anyway; do not roll back without
  re-examining.

**OPERATOR ACTION STILL PENDING (healthchecks.io dashboard): update every
check's schedule + grace period to the CIVO times** (daily staggered
02:00–04:00 UTC per runbook Appendix C, diary 03:20; recovery `*/5`;
SNOMED import Tue 14:00). With NF suspended, no pings arrive at the old
NF times → **every unchanged check will fire a false "late" alert from
tonight.**

**Healthchecks.io wiring DONE (2026-11-04):** the 11 ping URLs were
harvested from the Northflank job definitions BEFORE decommissioning
(they would have been lost Thursday) into the git-ignored `k8s/config.env`
as `HC_PING_*` keys (capability URLs — never in the public manifests).
`k8s/cronjobs.yaml` + `k8s/migrate-job.yaml` commands now ping on success
via `sh -c '... && if [ -n "$HC_PING_X" ]; then curl ...; fi'` — unset = no
ping (self-hosters unaffected). Verified end to end with a manual
`create job --from=cronjob/process-data-governance` run. REMAINING
(operator, healthchecks.io dashboard): create checks + URLs for the two
Civo-only jobs (`HC_PING_PROCESS_RECOVERY_TIME_DELAYSS`, placeholders in
config.env — recovery is every 5 min, snomed import weekly Tue 14:00) and
UPDATE EVERY CHECK'S SCHEDULE to the Civo run times (02:00–04:00 UTC
staggered — NOT the old Northflank times; recovery = 5-min period).

**NetworkPolicy near-miss (found + fixed 2026-11-04, same day as apply):**
the first revision of `checktick-db-ingress` allowed only web /
instance / operator pods — and SILENTLY BLOCKED EVERY CRONJOB POD from the
DB (a manual test job timed out reaching `checktick-db-rw`; tonight's
02:00 batch would have all failed, with healthchecks.io as the only
safety net). Root cause: the CronJob pod templates carried no labels at
all. Fix: `checktick.io/db-client: "true"` label on all 13 CronJob
templates + the pre-deploy Job, allowed explicitly in the policy (see
the comment in `k8s/postgres-networkpolicy.yaml`). Lesson: **a
NetworkPolicy's negative test must include every workload class that
legitimately talks to the protected service** (web AND batch).

## Session 11 (2026-11-04 evening): CVE-2026-98432 patched — all 3 nodes re-imaged + k8s 1.36.0

Driver: **CVE-2026-98432** (kernel IPv4 TCP handshake use-after-free,
CVSS 9.8, fix in 6.12.113) — all 3 nodes ran the vulnerable
`6.12.85-0-lts` as internet-exposed MPTCP listeners (Traefik on 80/443,
k3s API on 6443). Runbook `docs/upgrade-civo-node-image-cve-2026-98432.md`
(pre-written, now retired) drove the window. Window ~18:52–19:50 UTC,
operator present throughout.

### Findings that changed the plan (record for next time)

1. **`civo k8s upgrade` is IN-PLACE (k3s binary only) — it does NOT
   re-image the nodes.** The 1.35.0→1.36.0 upgrade completed in ~4 min
   with zero node replacement, zero unseal, zero pod churn (one API
   `ServiceUnavailable` blip + one transient `degraded` healthz while
   the k3s daemon bounced). Kernel unchanged after it — the CVE was
   still unpatched. The node IMAGE only changes via `civo k8s recycle
   CLUSTER --node NODE`.
2. **`civo k8s recycle` = cordon+drain → DELETE the instance → build a
   fresh node from the current image → it joins the pool.** Serial per
   node; ~4–8 min each (drain is fast; the PVC reattach dominates).
   Replacement nodes came up **Alpine v3.23 / kernel `6.18.60-0-lts`** —
   two LTS series newer than the runbook's 6.12.115 expectation.
3. **The External IP is a cluster-managed FLOATING IP.** When the node
   holding `74.220.17.170` was deleted, Civo moved the IP to a
   surviving node automatically. Across all 3 recycles it never
   changed → **no kubeconfig / Namecheap / `CIVO_KUBECONFIG` changes
   were needed at all** (the runbook's step-6 contingency never fired,
   but CHECK AFTER EVERY RECYCLE is still right).
4. **The db-ingress NetworkPolicy was blocking the CNPG operator's
   status API (port 8000)** — found in pre-flight, fixed before the
   window (see the 2c change-log rows): the operator polls
   `https://<instance>:8000/pg/status` and delivers switchover/demote
   via that API. The 04/11 policy revision allowed it on 5432 only →
   `Instance Status Extraction Error` on the cluster + `Cannot extract
   Pod status ... :8000: i/o timeout` every ~4s in the operator log.
   After adding operator→8000 + instance→8000 rules: log clean,
   `Cluster in healthy state`. **Then exercised for real by two primary
   switchovers during recycles — zero data loss, app never down.**
   (Without this fix, draining the primary's node would have STALLED
   against the `checktick-db-primary` PDB.)

### What actually happened (UTC actuals)

- 18:42 pre-upgrade base backup `completed` (backup #1 of 4).
- ~18:52 operator clicked Upgrade in the Civo UI → 1.36.0-k3s1 in-place
  by 18:57 (finding 1). Site up throughout.
- 19:09 **recycle #1 `blmru`** (replica + 1 web + floating IP): drained
  clean; `8ciwh` joined 19:13:47 on `6.18.60-0-lts`. Transient **404s
  (~2 min)** while the floating IP settled + the new node's traefik
  synced its routers — a fresh traefik pod answers TLS on the IP before
  it has the ingress routes; self-heals, do not panic.
- 19:17 backup #2 `completed`. 19:24 **recycle #2 `z4isg`** (PRIMARY):
  CNPG switchover `db-2`→`db-1` in ~40s (healthz degraded→ok), operator
  pod bounced to `s5y1n`, `db-2` rejoined as replica on `8ciwh` by
  19:32, `hwp2f` joined 19:27:04 on `6.18.60-0-lts`.
- 19:32 backup #3 `completed`. 19:33 **recycle #3 `s5y1n`** (Vault +
  primary + operator + floating IP): switchover `db-1`→`db-2` clean;
  `vault-0` storage reattached in 5.5 min (drill budget said 4–5) and
  came up `Initialized true, Sealed true` — **storage survived, the
  abort signal never fired**; operator unsealed with 3-of-4 production
  shares (~19:40); healthz fully ok ~10s later. `f985n` joined on
  `6.18.60-0-lts`.
- 19:41 **smoke test 19/19 PASS** in a live pod (login+2FA, ECIES
  submission, unlock, export decrypt, Vault escrow, SNOMED, audit).
- 19:46–19:49 Longhorn replenishment: both RWX volumes back to
  `healthy` (3 replicas) after the **600s
  `replica-replenishment-wait-interval`** — volumes served from ONE
  surviving replica until then; expect this lag after any node loss.

### Totals

- **All 3 nodes: Alpine v3.23 / kernel `6.18.60-0-lts` — CVE-2026-98432
  patched** (fix threshold was ≥ 6.12.113).
- k8s 1.35.0 → **1.36.0-k3s1**; CNPG operator (v1.30.x, supports 1.36)
  needed no change — as pre-verified.
- 4 base backups taken in-window (all `completed`); WAL chain unbroken;
  `ContinuousArchiving=True` throughout.
- User-facing downtime: ~40s blip per switchover + ~2 min 404 gaps per
  recycle + **~6 min sealed-Vault gap** for the final recycle's unseal.
  Total ≈ 10 min across the hour.
- External IP, DNS, kubeconfig, `CIVO_KUBECONFIG` — all unchanged.
- Certs both READY; Longhorn 2/2 volumes healthy; nightly 02:00 UTC
  backup expected on the new nodes (verify in the morning — the runbook
  record item).

## Session 12 (2026-11-05 evening): interim Vault backup + NF log export + OpenObserve deployed — and a node-memory cascade

Driver: next-steps items 2 (interim Vault storage backup, NF log export)
plus hardening item 4 (OpenObserve). All three landed; the evening also
produced two live findings that bit hard (see F1/F2).

### Done

1. **Interim Vault stop-copy backup DONE** (scale sts → 0 → helper pod on
   `data-vault-0` → tar streamed off-cluster → restore → operator unseal).
   Tarball 24 KB / 96 entries, sha256 `b6b9a9bd…`, at
   `~/vault-backup-2026-11-05/` — **custody: move to Bitwarden/offline, then
   delete the local copy** (superseded by the Raft migration, first hardening
   item). Sealed window ran ~47 min, not the planned 10 — see F1.
2. **NF historical logs exported + verified.** The running NF OpenObserve
   service turned out to be EMPTY: its 6 GiB `checktick-logs` volume was
   detached in a 2026-09-28 redeploy and the instance has run on ephemeral
   storage since. Attached the volume to a one-shot NF job (`northflank
   attach volume`, jobs have no `volumes` field in create-job), tarred /data
   (118 MB), downloaded + sha256-verified (`d8097c8d…`, 64.7 MB tarball at
   `~/nf-logs-export-2026-11-05/`), deleted the job, volume detached.
   Data spans **2026-06-20 → 06-26 only** (505,913 docs): the in-app
   OpenObserve exporter ran just one week before the stdout refactor killed
   it — the July→cutover NF-era logs only ever existed in Northflank's own
   platform log viewer and are gone with the account. Nothing more to
   export; NF side is clean for close-out.
3. **OpenObserve deployed on Civo** (`k8s/openobserve.yaml`, in kustomize):
   pinned `openobserve:v1.1.2`, Longhorn PVC, ClusterIP only (port-forward
   to use: `kubectl -n checktick port-forward svc/openobserve 5080:5080`).
   NF data dir restored into the PVC BEFORE first boot (scratch helper pod);
   v1.1.2 booted on it clean (forward metadata migration). Stream
   `default/default` carries the NF archive + would carry live logs;
   retention already 180 d. Auth: `openobserve-auth` Secret from git-ignored
   `k8s/openobserve.env` (keys documented in `k8s/openobserve.example.env`).
   **Rotate the root password in the UI after first login** (it is the NF-era
   credential).
4. **startupProbe bug fixed (live + manifest)**: the live Deployment had a
   `startupProbe` on `/healthz` (deep) — `failureThreshold 30 × 5s = 150s`,
   so a sealed Vault restart-looped the web pods every 2m41s and took the
   site down for the whole sealed window. Fixed in `k8s/web.yaml` (now
   `/api/health`, with comment) AND live-patched. Same class of lesson as
   the liveness rule in web.yaml — restarts cannot fix a seal.
5. **Collector built but REVERTED** — see F2. `k8s/log-collector.yaml` is
   committed but deliberately NOT in kustomization.yaml.
6. Backup chain re-verified after the CNPG interventions (`s/k8s-backup-verify`:
   all green, next run 02:00 UTC Nov 6).

### Findings that bit (record for next time)

1. **F1 — startupProbe on /healthz**: sealed Vault (planned window) → pods
   pass `/api/health` liveness but fail the deep startup probe → killed every
   150 s. Diagnosis: `kubectl get events` showed "Startup probe failed: 503"
   + "Container web failed startup probe"; container `Last State: Completed,
   exit 0` (graceful SIGTERM, so it looks *nothing* like a crash). The
   web pods ALSO 500'd `/api/health` intermittently — because DRF's throttle
   cache is DB-backed and the DB was unreachable while the CNPG primary was
   itself being killed (cascade below). `/api/health` is "trivial" only
   while the DB answers.
2. **F2 — the collector DaemonSet tipped the smallest node over its memory
   wall**: `8ciwh` (~2 GiB) already hosted the CNPG primary + cnpg operator
   + metrics-server + traefik (floating-IP node) + longhorn instance-manager
   + a web pod at ~79% requests. One fluent-bit (~150–250 Mi, tailing the
   CNPG pods' chatty csv+json triple-logs with Merge_Log) pushed it to
   101–109% actual → memory-reclaim stalls → EVERY pod's probes timed out in
   lockstep (localhost probes included!) → liveness-kill cascade (db-2 7×,
   traefik 9×, cilium-operator 7×, cnpg operator 14×, metrics-server 4×).
   The CNPG primary dying on a loop = the site down with 503/404 + the
   AdminEmailHandler → Graph 403 storm amplifying load.
   **Stabilisation that worked:** delete the DaemonSet → `kubectl cordon 8ciwh`
   (CNPG auto-switched the primary to db-1 on hwp2f in ~40 s, the documented
   cordon behaviour — no plugin needed) → delete the web pod on 8ciwh
   (rescheduled off the cordoned node) → delete the cnpg operator +
   metrics-server pods (Deployments — they rescheduled to healthy nodes).
   Cascade stopped; healthz 200; chain verified. **8ciwh left cordoned** —
   decide tomorrow: resize the node pool (proper fix) or `civo k8s recycle`
   the node (proven session-11 flow; db-2 is now a mere replica so risk is
   low) and uncordon.
3. **Unseal gotcha**: `s/k8s-vault-unseal`'s `printf | kubectl exec -i`
   piping failed ("Unseal submission failed") — the documented fallback
   `kubectl -n checktick exec -it vault-0 -- vault operator unseal`
   (interactive form) worked. Port the resume-script's capture-then-count
   verification pattern into the unseal script before next use.
4. **OpenObserve v1.x _json**: fluent-bit `format json_lines` (NDJSON) gets
   a 400 "trailing characters"; the documented `format json` (single JSON
   document per flush) works. Also: `[PARSER]` sections are rejected in the
   main config on fluent-bit 5.1.5 — must go in `Parsers_File`.
5. **Collector restart caveat**: ConfigMap changes do NOT restart DaemonSet
   pods; `rollout restart` after every collector config change.

### Late addition (22:00 UTC): Longhorn nightly off-cluster backups LIVE

Answered the "no backups for OpenObserve/Vault?" gap for every **Longhorn**
volume: `k8s/longhorn-backup.yaml` — RecurringJob `nightly-backup`, task
`backup`, **cron 03:30 UTC, retain 14, group `default`** (auto-covers any
future Longhorn PVC). BackupTarget patched to the SAME object-store bucket
the CNPG backups use, under `/longhorn` (secret `civo-object-store-creds`
in longhorn-system, created from the CNPG `checktick-db-backup-creds` keys
via a piped transform — values never printed). **Live-fire verified**: set
the cron 2 min ahead once → all three volumes (openobserve 640 MB, media
174 MB, snomed 5.8 GB) backed up, all `Completed`, BackupVolume listing
synced back FROM the bucket — data genuinely off-cluster. Gotchas for next
time: this Longhorn uses the **BackupTarget CRD**, not the old
`settings.longhorn.io backup-target` key (which no longer exists), and the
CRD rejects strategic-merge patches (`--type=merge` works). Longhorn's
minio-based S3 client is NOT affected by the Civo checksum quirk (unlike
AWS-SDK clients). PVC-annotation on-demand backup trigger
(`longhorn.io/backup`) silently does nothing on this version.

**Vault remains the only unbacked-up-scheduled component** — file storage has
no online snapshot path; the nightly-automatable fix is the Raft migration +
`vault operator raft snapshot save` CronJob (next-steps item 3, the designed
FIRST hardening item — needs an operator runbook + sealed window, do NOT
improvise). A stop-copy cron is NOT acceptable (unseal shares on a scheduled
job — breaks custody). Interim: the Bitwarden tarball from tonight.

**Node sizing answer** (user asked): Civo can't live-resize nodes, but
`civo k8s node-pool create checktick --name <pool> --nodes 3 --size
g4s.kube.large` adds a bigger pool to the SAME cluster — then drain the old
pool's nodes serially (session-11 recycle pattern per node: CNPG switchover
coordinated, floating IP follows) and `civo k8s node-pool delete` it. No
new cluster needed. Current pool is g4s.kube.medium (2 CPU/4 GB, ~2.25 Gi
allocatable/node — all three nodes measured at 79–101% of allocatable).

### Morning follow-up (2026-11-06 ~09:00)

1. **First fully-Civo night: green.** All 10 daily jobs completed on
   schedule, CNPG 02:00 backup landed, first production Longhorn nightly
   (03:30) completed, no restarts. One genuine job failure:
   process-recovery-time-delays ~21:40–21:55 (DB unreachable — the evening
   cascade), recovered same evening.
2. **The "4 failed healthchecks" were NOT failures**: three healthchecks.io
   checks (checktick-data-sync, checktick-prune-unconfirmed-email-accounts,
   checktick-downgrade-expired-subscriptions) still carry OLD Northflank-era
   schedules — they expected morning pings Nov 5, went "late", went UP when
   the Civo night batch pinged (02:20/02:40/03:00 — the downtime durations in
   the emails match exactly), then downgrade-expired went DOWN again on its
   stale schedule. healthchecks.io is a dead-man's switch: a schedule
   mismatch looks identical to a job failure. **Operator fix: set those
   three checks to the Civo times (02:20 / 02:40 / 03:00 UTC) and audit the
   other ten** (full table in the session log discussion; recovery */5,
   SNOMED Tue 14:00, NHS DD Sun 04:00 — NHS DD has still never run on Civo;
   manual test run recommended before Sunday).
3. **SNOMED excluded from Longhorn backups** (user decision — space/noise):
   the PVC is a derived artifact (built snomed.db already lives in the
   bucket under /snomed; import-snomed-db rebuilds the PVC from it).
   RecurringJob moved from the catch-all `default` group to named group
   `checktick-backup`; volumes opt in via the label
   `recurring-job-group.longhorn.io/checktick-backup=enabled` (⚠ the
   `recurringjob.longhorn.io/` prefix is for by-JOB association — the
   wrong prefix fails SILENTLY with no volumes matched, found live).
   Labelled: openobserve-data, checktick-media. Live-fire verified 09:22
   (two backups, no snomed); the two existing snomed backup sets deleted.
   New PVCs are no longer auto-covered — add the label when adding a PVC.
4. **Bucket reality** (s3 listing via scratch pod): longhorn/ 0.55 GB,
   db/ 0.09 GB, snomed/ 1.85 GB — ~2.5 GB total. Space is NOT currently
   a constraint.

### Deferred decisions (tomorrow)

- **NEXT SESSION — Vault Raft migration**: the draft runbook is
  `docs/vault-raft-migration.md` (pre-written 2026-11-06: current-state
  facts, design decisions incl. the CTO snapshot-custody sign-off, the
  window procedure, the snapshot CronJob spec, restore test, rollback).
  **Session 13 PREP landed 2026-11-06** (see below): ⚠ VERIFY flags
  resolved against the 1.21 CLI docs — the draft `migrate.hcl` stanza names
  were WRONG and are corrected — and every artifact is committed
  (`k8s/vault-snapshot.yaml`, `s/k8s-vault-snapshot-ceremony`, airgap
  rules in `vault.yaml`, the scratch migrate helper). What remains is
  OPERATOR work: the age keypair, the window ceremonies (3-of-4 shares),
  the healthchecks.io check, the first-run + restore-test verification.
  This is the LAST unautomated backup.

- Node pool resize (the create-pool/drain/delete path above) vs recycling
  `8ciwh` (it is cordoned right now).
- Vault Raft migration runbook + snapshot CronJob (the last unautomated
  backup).
- Collector redeploy options (see the ⚠ note in `k8s/log-collector.yaml`).
- Graph email 403s (`sendMail` Forbidden for admin@checktick.uk) — separate
  pre-existing issue, surfaced by the alert storm.
- AdminEmailHandler fires on every ERROR log → a healthz 503 loop turns into
  an outbound-email storm (self-amplifying during any outage). Consider
  `requirement` filters or rate limiting.
- Rotate the OpenObserve root password (UI) after first login.

## Session 13 (2026-11-06): Vault Raft migration PREP — ⚠ VERIFY resolved, artifacts built

Driver: the deferred decision above (the last unautomated backup). The
window itself is still operator-pending (needs the 3-of-4 shares twice);
this session made it mechanical. The runbook now carries a "Verification
notes" section — every flag was checked against the HashiCorp 1.21 CLI
docs, not assumed.

### Done

1. **⚠ VERIFY flags resolved — and they mattered**: the draft
   `migrate.hcl` stanza names (`storage` / `destination`) are WRONG —
   1.21 uses **`storage_source` / `storage_destination`**
   (docs/commands/operator/migrate). The window would have died on a
   config error. Also verified: migrate is offline + resumable
   (`-start <prefix>`), a lock key blocks Vault start mid-migration
   (`-reset` clears it), the destination must be UNINITIALISED, and the
   source is untouched except the lock (the rollback holds).
   `vault operator raft snapshot save/restore/inspect` verified
   (docs/commands/operator/raft) — **restore returns BEFORE completing**:
   wait for `post-unseal setup complete` + `vault is unsealed` in the
   server log. Raft stanza verified (docs/configuration/storage/raft):
   `cluster_addr` REQUIRED, no `ha_storage`, `disable_mlock = true`
   recommended (already set). `age` 1.2.1 confirmed in alpine v3.21
   community → the encrypt container is viable. Live state re-verified
   from the cluster: `1.21.4`, Storage Type `file`, Sealed false — the
   window has NOT run. **Pre-window live layout check caught a THIRD
   error**: the data-vault-0 volume root IS the storage dir (`core/`,
   `logical/`, `sys/` at the PVC root — NO `file/` subdir); the draft's
   source path `/vault/storage/file` was wrong → migrate source is
   `/vault/storage`, and the runbook's rollback + cleanup paths are
   corrected to match.
2. **`k8s/vault-snapshot.yaml` built** (committed, deliberately NOT in
   kustomization.yaml — the postgres-cnpg pattern; apply out-of-band
   after the window): CronJob 03:45 UTC (after Longhorn 03:30), pod
   label `checktick.io/vault-snapshot=true`, tmpfs working volume (the
   raw barrier snapshot never touches node disk). initContainers:
   `snapshot` (vault CLI, AppRole login, `raft snapshot save`) →
   `encrypt` (`alpine:3.21` + `apk add age`, `age -r $AGE_RECIPIENT`,
   rm the raw tar); main container `upload`: aws-cli + the Civo
   checksum env pair, creds `checktick-db-backup-creds`, uploads to
   `s3://checktick-backups/vault/`, prunes to the 14 newest, pings
   `HC_PING_VAULT_SNAPSHOT` on success only (optional
   configMapKeyRef → self-hosters unaffected). AGE_RECIPIENT is
   deliberately NON-optional: a missing recipient must FAIL the job
   rather than upload an unencrypted snapshot.
3. **`s/k8s-vault-snapshot-ceremony` built** (generate-root → policy
   `vault-snapshot`, `sys/raft/snapshot/save` ONLY → batch-token
   AppRole, 90d secret_id, NO default policy → k8s Secret
   `vault-snapshot-approle` → root revoke). Same captured-output
   verification pattern as `s/k8s-vault-ceremony`. Rotation = re-run at
   the quarterly restore rehearsal; a missed rotation fails the nightly
   job and the healthchecks.io dead-man alert fires same-night.
4. **Airgap rules committed in `k8s/vault.yaml`**: the snapshot-pod
   ingress grant (the label IS the access grant — the db-client pattern)
   + a scoped 8201 self-allow. FINDING: the previous deny-all egress
   would have silently blocked a single-node raft Vault dialing its OWN
   cluster port via the Service — the failure mode is a hung unseal /
   leadership at the window, found only because the docs were read with
   that question in mind. Both rules are additive → safe pre-window;
   negative-test after apply (an UNlabelled pod must still time out on
   8200).
5. **`k8s/scratch-vault-raft-migrate.yaml`** (git-ignored): the one-shot
   migrate helper pod + the CORRECTED migrate.hcl (applied, never
   committed).
6. Runbook updated (verification notes, corrected configs, artifact
   pointers, first-run verification commands); kustomization.yaml NOTE
   added for the excluded snapshot manifest.

### Still operator (the window)

- age keypair (`age-keygen`): private → Bitwarden; recipient → the
  out-of-band ConfigMap `vault-snapshot-config` (command in the
  vault-snapshot.yaml header — public material, but it identifies the
  operator's backup identity, so it never enters the repo)
- the window per the runbook (two share ceremonies), then
  `s/k8s-vault-snapshot-ceremony` → `kubectl apply -f
  k8s/vault-snapshot.yaml` → healthchecks.io check (daily 03:45) +
  `HC_PING_VAULT_SNAPSHOT` in config.env → manual first-run job green →
  restore test → THEN delete the old file data at the volume root, retire
  the interim tarball note, mark hardening item 1 done, and add the change
  to the compliance infrastructure change log.

## Session 14 (2026-11-06 evening): Vault Raft migration EXECUTED + encrypted nightly snapshots LIVE

Driver: session 13's prep + the operator's go. The last unautomated
backup is now automated: nightly 03:45 UTC, age-encrypted, off-cluster,
retention 14.

### What happened (UTC actuals)

1. **Activity check first** (17:41): app logs showed zero authenticated
   users all day (bot noise only — failed OIDC callbacks, CSRF-rejected
   scanner hits; last event 14:47). Traefik access logging is OFF (only
   internal CRD-watch noise) — noted as a monitoring gap.
2. **Window 17:48:47 → ~18:03** (~15 min sealed, on estimate): scale 0 →
   helper pod → fresh stop-copy (29 KB tarball, sha256 `8c8b347f…`, at
   `~/vault-backup-2026-11-06-pre-raft/` — Bitwarden custody pending) →
   `vault operator migrate` (all keys copied in <1 s) → raft ConfigMap
   + `/vault/storage` remount applied → scale 1 → operator unseal
   (3 shares). StatusCake fired + recovered as expected; no web restart
   loops (the fixed `/api/health` startupProbe held).
3. **Verification**: `vault status` Storage Type raft, HA active,
   committed=applied index; `/healthz` fully ok (the deep check proves
   the migrated AppRole + platform key); **smoke 19/19** — the escrow KV
   write→read→delete exercises the raft WRITE path, not just reads.
   `raft list-peers`: vault-0 leader (peer registered as `127.0.0.1:8201`
   — the migrate.hcl loopback cluster_addr; harmless single-node,
   revisit if a peer is ever added).
4. **Snapshot pipeline LIVE**: age keypair minted (recipient in the
   `vault-snapshot-config` ConfigMap; private key → Bitwarden), the
   ceremony minted the `vault-snapshot` AppRole, CronJob applied
   out-of-band, manual first run GREEN end-to-end: AppRole login → raft
   snapshot save (29 KB) → age encrypt (raw tar rm'd from tmpfs) → S3
   upload (`vault-raft-2026-11-06T184809.tar.age`, 29,575 bytes) →
   prune. Object independently confirmed via an aws-cli listing pod.
   Airgap negative-tested: an UNlabelled pod times out on 8200 (the
   session-10 lesson applied).
5. **RESTORE TEST PASSED (CT-03)** — the runbook-closer, same evening:
   newest `.age` object downloaded + sha256-verified → decrypted on the
   operator laptop (Bitwarden age key, never in-cluster) → `snapshot
   inspect` (full key inventory) → restored into a fresh scratch Vault
   (`snapshot restore -force`) → **unsealed with the production 3-of-4
   shares** → verified: production cluster identity
   (`vault-cluster-978f63d7`), `checktick-app` AppRole login with the
   production credentials, count-only read of
   `secret/data/platform/master-key`. Scratch STS + PVC (a production
   data copy) deleted same-session. Recorded in
   `docs/compliance/restoration-test-log.md` (CT-03).

### Found live (record for next time)

1. **`vault operator migrate` does NOT mkdir the destination** —
   `mkdir /vault/storage/raft` first, else `failed to open bolt file:
   open /vault/storage/raft/vault.db: no such file or directory`.
   "Destination must not be initialised" = an EMPTY dir must EXIST.
2. **`vault read -format=json` PRETTY-PRINTS** (space after the colon,
   arrays across lines) — compact-JSON grep patterns false-negative a
   SUCCESSFUL write. Bit the ceremony's role verification; recovered
   via a new `--resume` flag (re-enter the live root token, no second
   generate-root). Same lesson class as the grep -q rule.
3. **The snapshot endpoint moved**: 1.21.4 `vault operator raft
   snapshot save` calls `GET /v1/sys/storage/raft/snapshot` — NOT the
   older `sys/raft/snapshot/save` (which the CLI docs never state; the
   first policy 403'd at the first run). Policy is now read+update on
   `sys/storage/raft/snapshot` only. Cost: one extra generate-root
   ceremony.
4. **`snapshot restore` needs `-force` for cross-cluster restores** —
   the default hash check rejects a snapshot sealed under different
   unseal keys (a custody feature, not a bug).
5. **Post-restore, the running process serves its OLD in-memory seal
   config** — unsealing before a process restart fails with
   `invalid key: crypto/aes: invalid key size 33`; bounce the pod, the
   restored 4-of-3 config is then served and the production shares
   work.
6. **A fresh raft Vault does not create its own storage path either**
   (same as the migrate) — `mkdir -p` before start or the server exits
   in a loop. Also: `kubectl cp` needs `tar` IN the container (the
   aws-cli image lacks it — alpine + `apk add aws-cli` works) and a
   pod with no readiness probe is "ready" before its work finishes —
   don't cp out of it until the logs confirm the download.

### Still open

- ~~healthchecks.io wiring~~ **DONE**: check created (daily 03:45),
  `HC_PING_VAULT_SNAPSHOT` in config.env, ping delivered by a manual
  verification run. GOTCHA found live: `--from-env-file` keeps the value
  RAW — an inline comment after the URL became part of it (`curl: (3)
  URL rejected`); env files support comments only on their OWN lines.
  Rule added to k8s/config.example.env.
- ~~Restore test~~ **DONE — PASSED (CT-03)**, see What happened #5.
- ~~Pre-raft tarball → Bitwarden → delete local~~ **DONE** (verified:
  local copies gone).
- ~~Post-pass cleanup~~ **DONE (2026-11-06 ~19:57 UTC)**: the old
  file-storage dirs deleted from the production volume root via vault-0
  itself (no sealed window — the dirs were inert siblings of raft/);
  the volume root now holds only raft/ + lost+found; healthz fully ok
  throughout. The Bitwarden pre-raft tarball is now the pre-migration
  rollback of last resort. The runbook + this file retire at the Phase 6
  close-out as sequenced.

## Known state at session close (session 9, 2026-11-03)

- **PRODUCTION IS LIVE ON CIVO** — `https://checktick.uk` → 200, `/healthz`
  fully ok, both certs READY, 13 CronJobs active, DB cluster healthy with
  `ContinuousArchiving: True`, web pinned to `0.24.2`.
- **Northflank is STOPPED, NOT deleted** — 48 h rollback window per runbook
  Phase 5, expires **~2026-11-05 22:46 UTC**. Rollback = DNS back to the
  Northflank CNAME + resume services + return the `vault-data` volume +
  unseal (runbook Appendix A). Do NOT decommission before expiry.
- `SITE_URL=https://checktick.uk` and the overlay applied; `ALLOWED_HOSTS` in
  the overlay carries both hostnames.
- **CRITICAL until `ALLOWED_HOSTS_EXTRA` ships (Phase 6):** the public
  hostnames in `ALLOWED_HOSTS` live ONLY in the live Deployment patch
  (`k8s/scratch-allowhosts-patch.yaml`, git-ignored). `deploy-civo.yml` does
  NOT re-apply manifests (`set image` only) so the patch survives every
  workflow deploy — but any manual `kubectl apply -f k8s/web.yaml` (or
  `-k k8s/`) RESETS it and the site 400s; re-apply the patch afterwards.
- `HOSTING_*` (stale Northflank API creds) dropped from `checktick-secrets`
  at T+20; `SECRET_KEY` rotated in-window; AppRole is the migrated-Vault
  mint.
- Object store: dead-POC debris purged (old base backup + test file);
  `db/` now holds only the current cluster's WALs + nightly base backups.
- Git-ignored tooling (this machine, `k8s/scratch-*`, NEVER commit):
  sessions 5–8 as previously listed, PLUS session 9:
  `scratch-cutover-vault-copy.sh` (T+2 — has the run-id JSON parse bug,
  session 9), `scratch-cutover-vault-restore.sh` +
  `scratch-cutover-vault-ceremony.sh` (T+5 — ceremony has the grep-pipefail
  false-negative), `scratch-cutover-vault-resume.sh` (the FIXED verification
  pattern — port it back before reuse), `scratch-cutover-db.sh` (T+10,
  clean), `scratch-cutover-counts-*.txt|diff`, `scratch-allowhosts-patch.yaml`
  (window version: BOTH hostnames).

## Next steps (next session)

1. ~~**VERIFY THE 02:00 UTC BACKUP (2026-11-04)**~~ **DONE (session 10): the
   schedule was silently blocked** — see session 10 for the compound root
   cause (stuck non-terminal Backup from Nov 2 + dead pod IP) and the fix.
   First restorable chain landed 2026-11-04 09:33 UTC (`completed`);
   next nightly 2026-11-05 02:00 UTC — verify THAT one lands too, since
   the schedule only just resumed.
2. **Thursday ~22:46 UTC (2026-11-05): rollback window expires** → Phase 6
   close-out. FRESH-SESSION HANDOFF (written 2026-11-05 morning): read this
   item + runbook Phase 6 + docs/civo-kubernetes-operations.md; the branch
   `chore/civo-k8s-migration-closeout` is pushed (PR opens at close-out).
   Remaining work, in order (DONE items marked):

   - [x] Deploy-trigger swap (`docker-publish.yml` dispatches Deploy (Civo))
   - [x] Documentation sweep + DPIA/processor/supplier records (Civo DPA terms
     recorded; ISO 27001/SOC 2 + sub-processor list requested from Civo
     05/11 — acknowledged, reply awaited; fill the `[confirm]` markers in
     supplier-register / supplier-assurance-mapping / annual-security-
     validation / dtac when it arrives)
   - [x] healthchecks.io: all 13 checks re-scheduled to the Civo run times
     (02:00–03:20 UTC daily staggered, recovery `*/5`, SNOMED Tue 14:00,
     NHS DD Sun 04:00 — first fully-green night expected 05→06/11)
   - [ ] **Interim Vault storage backup BEFORE the NF account closes**
     (Civo has NO ad-hoc volume snapshot for k3s-attached volumes and managed
     nodes are not snapshot-schedule instances — the stop-copy ceremony is
     the only clean interim): scale `statefulset/vault` to 0 → helper pod
     mounts `data-vault-0` at /vault/file → tar the storage → `kubectl cp`
     the tarball OFF-cluster (laptop → Bitwarden/offline per custody) →
     delete helper, scale back to 1 → **operator unseals via
     `s/k8s-vault-unseal`**. ~10-min sealed window: /healthz 503 → StatusCake
     fires (expected). The copy is superseded when the Raft migration +
     nightly snapshot CronJob land (FIRST hardening item after close-out).
   - [ ] Just BEFORE account closure: export Northflank operational logs if
     retention requires
   - [ ] Delete Northflank project data + close the account
   - [ ] Revoke the Northflank API token at the provider + remove the token
     line from the local git-ignored `.env`
   - [ ] Delete the `NORTHFLANK_WEBHOOK_URL` GitHub secret (unused since the
     deploy-trigger swap)
   - [ ] `vault operator rekey` (operator ceremony, 3-of-4 shares — decide the
     share medium at this point) + revoke the drill API token
   - [ ] Remove `staging.checktick.uk` from `ALLOWED_HOSTS_EXTRA` in
     `k8s/config.env` + `ingress.local.yaml`; re-apply the overlay ConfigMap
   - [ ] Delete the decommission scratch batch: `scratch-nf-*` (3 — secure
     delete, NF creds), `scratch-drill-db-*` (5, superseded by
     docs/restore-rehearsal.md + s/k8s-restore-rehearsal),
     `scratch-barman-test.yaml`. KEEP: `scratch-allowhosts-patch.yaml`
     (live until 0.25.0 deploys), `config.env`/`secrets.env`/
     `ingress.local.yaml`, `scratch-clusterissuer.yaml` (Vault-TLS backlog
     starting point), and the vault-side drill tooling (`drill-vault-*`,
     `decrypt.*`, `mech-*`, `teardown.sh`, `web.yaml`, `survey.env`,
     `revoke-root.sh`)
   - [ ] Delete this file and `docs/migration-northflank-to-civo.md`; fix
     inbound links: `docs/README.md`, `k8s/README.md` (x3), `k8s/vault.yaml`,
     `k8s/postgres-cnpg.yaml`, `.github/workflows/deploy-civo.yml` (all
     reference the runbook doc path)
   - [ ] Commit all of the above to the branch, then open the PR
   - [ ] Merge → publish 0.25.0 → Deploy (Civo) fires (first live exercise of
     the swapped trigger) → post-deploy: apply the overlay, `kubectl apply -f
     k8s/web.yaml` (retires the live ALLOWED_HOSTS env patch), verify
     checktick.uk responds (staging 400s after its removal from
     ALLOWED_HOSTS_EXTRA — intended), then delete
     `k8s/scratch-allowhosts-patch.yaml`
   - [ ] Next morning: verify the 02:00 backup via `s/k8s-backup-verify`
3. **Vault backup (top hardening priority):** migrate file storage → Raft,
   then a nightly `vault operator raft snapshot save` CronJob. The stop-copy
   alternative puts unseal shares on a cron — breaks custody. Until then the
   Vault has NO scheduled backup (tonight's copy was manual, tarball deleted).
4. ~~**`ALLOWED_HOSTS_EXTRA` in settings.py** (needs an image release) — kills
   the scratch-patch workaround and the manifest override comment.~~
   **DONE (2026-11-04):** implemented with tests in 0.25.0 (version bumped in
   pyproject.toml). On push-to-main the publish workflow builds the image and
   dispatches Deploy (Civo) — first live exercise of the swapped trigger.
   POST-RELEASE (after 0.25.0 is live): apply the overlay
   (`kubectl create configmap checktick-config-local -n checktick
   --from-env-file=k8s/config.env --dry-run=client -o yaml | kubectl apply -f -`),
   then `kubectl apply -f k8s/web.yaml` (retires the live env patch), verify
   checktick.uk + staging respond, then delete
   `k8s/scratch-allowhosts-patch.yaml`.
5. ~~**Port the resume script's robust verification** back into
   `scratch-cutover-vault-ceremony.sh` before that script is ever reused.~~
   **DONE (2026-11-04, superseded):** the cutover tooling is deleted; the
   robust captured-output verification (capture first, `grep -c` counts,
   never `grep -q` pipelines under pipefail) is ported into
   `scratch-drill-vault-ceremony.sh` — the script that will actually be
   reused.
6. Quarterly restore rehearsal (feeds `docs/compliance/restoration-test-log.md`)
   — the drill tooling is directly reusable.
7. ~~**(2026-11-04, planned evening) Node-image upgrade for CVE-2026-98432**~~
   **DONE (session 11, 2026-11-04 evening):** k8s 1.35.0→1.36.0 (in-place) +
   all 3 nodes recycled onto the patched image (Alpine v3.23 / kernel
   6.18.60-0-lts); smoke 19/19; records in the compliance change log 2c;
   temp runbook deleted. Key learnings in the session 11 section (in-place
   upgrade ≠ re-image; `civo k8s recycle` is the image path; the external
   IP is a floating IP that follows the cluster; the CNPG operator needs
   port 8000 in the db-ingress policy). Scratch-file disposition decided
   2026-11-04: the dead POC
   vault key material + stale pre-cutover secret exports are deletable now;
   the cutover/NF tooling deletes at decommission (see session 10 notes).
   **Executed 2026-11-04 evening:** POC key material + stale exports AND the
   cutover tooling (all `scratch-cutover-*`) deleted — the resume script's
   verification pattern was ported into `scratch-drill-vault-ceremony.sh`
   first (next-steps item 5). The NF tooling, the NF-source DB drill tooling
   (`scratch-drill-db-run.sh` et al., superseded by
   `docs/restore-rehearsal.md`) and `scratch-barman-test.yaml` follow at
   decommission.

History (all complete): items 1–6 below are the closed pre-cutover next-steps,
kept for the record.

1. ~~Resend confirmation emails~~ **DONE (session 6)**
1. ~~Resend confirmation emails~~ **DONE (session 6):** real email delivery
   verified end to end — fresh account created on staging, confirmation
   email received and clicked. (Optional: resend for the two older
   `email_confirmed=False` test accounts if you want them usable.)
2. ~~Pin the live web image off `latest`~~ **DONE (session 8):** Deploy
   (Civo) dispatched with `image-tag: 0.24.2` after the WAL-archive outage
   was fixed — run green end-to-end, live Deployment pinned, live ==
   manifest so `kubectl apply -k k8s/` no longer resets the image.
3. ~~Verify which redirect URIs matched for staging OIDC~~ **Recorded
   (session 6):** the redirect URI sent on staging is
   `https://staging.checktick.uk/oidc/callback/` (mozilla-django-oidc
   absolutifies from the request host; the hardcoded prod
   `OIDC_REDIRECT_URI` is unused). Both app registrations carry it — Google
   completes on staging, Azure gets past redirect validation.
   ~~REMAINING: user retest of the Microsoft button with the personal
   M365 account~~ **DONE (operator, 2026-11-03):** the Microsoft button
   completes the full loop on staging (tenant `common`).
4. ~~POC exit criteria left~~ **DONE (session 5):** the `kubectl apply -k
   k8s/` idempotency check and the tear-down/re-apply test both PASSED —
   Phase 1 is complete. `CIVO_KUBECONFIG` GitHub secret is also set
   (verified via `gh secret list`) — the Deploy (Civo) workflow is
   dispatchable.
5. ~~Runbook Phase 3 rehearsal planning~~ **DONE (session 7):** both drills
   have tooling under `k8s/scratch-drill-*`, mechanically validated end to
   end against staging data (smoke 19/19 against the moved Vault storage;
   DB drill exact count match). The real production-data drills await the
   operator inputs listed in the Session 7 section. NOTE for the drill: the
   Vault storage-copy carries whatever policy the source had at copy time —
   the staging Vault is already fixed, but the PRODUCTION copy from Northflank
   would carry the stale policy if the stanza is not applied there first
   (pre-cutover checklist item, runbook Phase 3).
   **Phase 2 is COMPLETE and re-verified on the rebuilt environment** (all
   provider-level creds rotated + staged in `k8s/secrets.env`, restored as
   `checktick-secrets`, proven by the healthz-gated rollouts, the live
   Graph token fetch, and the post-rebuild smoke 19/19). The only
   rotation items left are deliberately cutover-time (runbook Phase 2):
   new `SECRET_KEY` swapped inside the freeze window (T+20), and the fresh
   AppRole `secret_id` + fixed `checktick-app` policy minted on the
   MIGRATED Vault after the T+2 storage copy (one root ceremony —
   runbook Phase 4 T+5).
6. Phase 6 backlog candidates: `ALLOWED_HOSTS_EXTRA` in settings.py (kills
   the scratch patch); open SNOMED readers as
   `file:...?mode=ro&immutable=1` in healthz/resolver/seed so a WAL-mode
   snomed.db is readable on ANY read-only mount (needs an image release;
   the init-container conversion makes this non-urgent).

## Pointers

- Runbook + findings ledger: `docs/migration-northflank-to-civo.md`
- Walkthrough + validation commands: `k8s/README.md`
- Deploy workflow: `.github/workflows/deploy-civo.yml` — `CIVO_KUBECONFIG`
  GitHub secret is set (verified session 5); dispatchable from Actions
- SNOMED build workflow: `.github/workflows/build-snomed-db.yml` — GitHub
  secrets `TRUD_API_KEY`, `CIVO_S3_ACCESS_KEY`, `CIVO_S3_SECRET_KEY` are set
