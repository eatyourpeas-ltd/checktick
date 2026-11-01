# POC Status — Civo Migration (session handoff)

Working state of the Civo migration POC — the `civo-migration` branch is now
merged to `main` (v0.24.1 shipped). Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — its Phase 0 "findings"
ledger records every environment discovery so far) and `k8s/README.md`.

Last updated: 2026-11-01 (end of session 4).

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
- The `zdt-test` pod is still running (1 req/s loop) — delete it when done
  with the POC. Its cumulative FAIL count is still **zero** after five
  rollouts (three restarts + the WAL-fix patch rollout + the restart
  before it).

## Next steps (next session)

1. **Resend confirmation emails** for the two test accounts (Graph works,
   SITE_URL points at staging) → click the links. The Phase 1 round-trip
   itself is DONE (smoke 19/19 incl. the recovery-escrow path) — this is
   now only about real email delivery to the real accounts.
2. **Pin the live web image off `latest`**: the live Deployment still runs
   `ghcr.io/eatyourpeas-ltd/checktick:latest` — run Deploy (Civo) with an
   explicit `image-tag: 0.24.1` to pin it (also proves the tagged CI path
   end to end).
3. Verify which redirect URIs in the Google/Azure app registrations matched
   for staging OIDC (signup worked — record the exact entries).
4. POC exit criteria left: `kubectl apply -k k8s/` idempotency check (re-apply
   the ALLOWED_HOSTS patch after) and the tear-down/re-apply test.
5. Runbook Phase 3 rehearsal planning (Vault storage-migration drill, DB
   restore drill, timing table). NOTE for the drill: the Vault
   storage-copy carries whatever policy the source had at copy time — the
   staging Vault is already fixed, but the PRODUCTION copy from Northflank
   would carry the stale policy if the stanza is not applied there first
   (pre-cutover checklist item, runbook Phase 3).
6. Phase 6 backlog candidates: `ALLOWED_HOSTS_EXTRA` in settings.py (kills
   the scratch patch); open SNOMED readers as
   `file:...?mode=ro&immutable=1` in healthz/resolver/seed so a WAL-mode
   snomed.db is readable on ANY read-only mount (needs an image release;
   the init-container conversion makes this non-urgent).

## Pointers

- Runbook + findings ledger: `docs/migration-northflank-to-civo.md`
- Walkthrough + validation commands: `k8s/README.md`
- Deploy workflow: `.github/workflows/deploy-civo.yml` — needs
  `CIVO_KUBECONFIG` GitHub secret (still to set)
- SNOMED build workflow: `.github/workflows/build-snomed-db.yml` — GitHub
  secrets `TRUD_API_KEY`, `CIVO_S3_ACCESS_KEY`, `CIVO_S3_SECRET_KEY` are set
