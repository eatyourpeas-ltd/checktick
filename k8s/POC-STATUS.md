# POC Status — Civo Migration (session handoff)

Working state of the Civo migration POC — the `civo-migration` branch is now
merged to `main` (v0.24.1 shipped). Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — its Phase 0 "findings"
ledger records every environment discovery so far) and `k8s/README.md`.

Last updated: 2026-11-02 (end of session 6).

## Environment

- Civo Kubernetes `checktick` cluster, LON1, 3 × medium nodes (2 vCPU/4 GB),
  Kubernetes 1.35.0
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

- Vault: single node, initialised (throwaway 4/3 Shamir), unsealed, AppRole
  configured via `vault/setup_vault.py`; `vault-0` 1/1. Root token revoked.
  Manifest fixes (all POC findings, commented in `vault.yaml`): `fsGroup`,
  `disable_mlock`, direct `command:` invocation.
- PostgreSQL 17 (CNPG): 2 instances healthy, WAL archiving verified end to
  end to `s3://checktick-backups/db` (requires the SigV4 `region` SecretKeySelector
  and the S3 checksum env vars — see Cluster spec.env). Nightly base backup
  02:00 UTC.
- Migrate job (`checktick-predeploy`): **passed** — full credential chain
  Django → Secret → service → CNPG verified; migrations and syncs complete.
- Web Deployment: 2 replicas, Longhorn RWX PVCs bound (media + SNOMED share),
  running `ghcr.io/eatyourpeas-ltd/checktick:latest` (the roll-out test pins
  it to a released tag — see next steps).
- Rotated credentials pushed: `checktick-secrets` + `checktick-config-local`
  re-applied from the cycled files; rollout was healthz-gated (so the rotated
  `DATABASE_URL` + Vault AppRole are proven working) and a live Graph token
  fetch verified the email creds (the signup-time 401 is fixed).
- `/healthz`: **full `status: ok`** — `db: ok`, `vault: ok`, `snomed: ok`
  (SNOMED verified end to end this session), via pod localhost, Service DNS,
  and public HTTPS.
- Zero-downtime proof: **PASSED** — the `zdt-test` curl loop pod has been
  running through **three** full `rollout restart`s with zero FAILs.
- Ingress + TLS: Traefik routes `staging.checktick.uk`; cert-manager
  certificate `READY True` (Let's Encrypt); public HTTPS serving 200.
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

## Known state at session close

- `SITE_URL=https://staging.checktick.uk` in the overlay — applied to the
  cluster; running pods pick it up at the next roll. Cutover flips it back
  to `https://checktick.uk`.
- The staging hostname in `ALLOWED_HOSTS` is a live Deployment patch
  (`k8s/scratch-allowhosts-patch.yaml`, git-ignored). `deploy-civo.yml`
  does NOT re-apply manifests (`set image` only) so the patch survives its
  roll-outs — but any `kubectl apply -f k8s/web.yaml` (or `-k k8s/`) resets
  it; re-apply the patch afterwards. Proper fix (`ALLOWED_HOSTS_EXTRA` in
  settings.py) is runbook Phase 6 backlog.
- The `zdt-test` pod was deleted at the end of session 5 (final tally
  recorded above: **zero FAILs across five rollouts**).
- Git-ignored POC tooling added in session 5: `k8s/scratch-vault-ceremony.sh`
  (fresh-Vault ceremony), `k8s/scratch-revoke-root.sh` (root-token revoke),
  `k8s/scratch-export-*.json` (the four out-of-band objects — needed for
  any future teardown test), `k8s/scratch-vault-init.json` +
  `k8s/scratch-vault-setup.txt` (current ceremony output). All match the
  `k8s/scratch-*` gitignore patterns; NEVER commit them.

## Next steps (next session)

1. ~~Resend confirmation emails~~ **DONE (session 6):** real email delivery
   verified end to end — fresh account created on staging, confirmation
   email received and clicked. (Optional: resend for the two older
   `email_confirmed=False` test accounts if you want them usable.)
2. **Pin the live web image off `latest`**: the live Deployment still runs
   `ghcr.io/eatyourpeas-ltd/checktick:latest`. The k8s manifests are now
   pinned to released tags (`0.24.2` — the current release, superseding the
   `0.24.1` noted here earlier) and the Deploy (Civo) `image-tag` input is
   now required. REMAINING: dispatch Deploy (Civo) with `image-tag: 0.24.2`
   to pin the live Deployment (also proves the tagged CI path end to end).
   Once dispatched, live == manifest, so `kubectl apply -k k8s/` no longer
   resets the image to `latest`.
3. ~~Verify which redirect URIs matched for staging OIDC~~ **Recorded
   (session 6):** the redirect URI sent on staging is
   `https://staging.checktick.uk/oidc/callback/` (mozilla-django-oidc
   absolutifies from the request host; the hardcoded prod
   `OIDC_REDIRECT_URI` is unused). Both app registrations carry it —
   Google completes on staging, Azure gets past redirect validation.
   REMAINING: user retest of the Microsoft button with the personal
   M365 account (tenant value now `common` — see session 6).
4. ~~POC exit criteria left~~ **DONE (session 5):** the `kubectl apply -k
   k8s/` idempotency check and the tear-down/re-apply test both PASSED —
   Phase 1 is complete. `CIVO_KUBECONFIG` GitHub secret is also set
   (verified via `gh secret list`) — the Deploy (Civo) workflow is
   dispatchable.
5. Runbook Phase 3 rehearsal planning (Vault storage-migration drill, DB
   restore drill, timing table). NOTE for the drill: the Vault
   storage-copy carries whatever policy the source had at copy time — the
   staging Vault is already fixed, but the PRODUCTION copy from Northflank
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
