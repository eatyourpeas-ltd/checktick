# POC Status — Civo Migration (session handoff)

Working state of the `civo-migration` branch POC. Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — its Phase 0 "findings"
ledger records every environment discovery so far) and `k8s/README.md`.

Last updated: 2026-11-01 (end of session 3).

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
- `/healthz`: `db: ok`, `vault: ok`, `snomed: unavailable` (pending the CI
  build), via pod localhost, Service DNS, and public HTTPS.
- Zero-downtime proof: **PASSED** — the `zdt-test` curl loop pod has been
  running through **three** full `rollout restart`s with zero FAILs.
- Ingress + TLS: Traefik routes `staging.checktick.uk`; cert-manager
  certificate `READY True` (Let's Encrypt); public HTTPS serving 200.
- CronJobs: all 13 applied (incl. `import-snomed-db`);
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
  with the POC.

## Next steps (next session)

1. **PR `civo-migration` → `main` with the 0.24.0 minor bump** (bump is in
   the PR). On merge: docker-publish publishes `0.24.0` + `latest` and fires
   the Northflank webhook — production gets the 2FA fix. Nothing automatic
   happens on Civo.
2. **Civo roll-out test** (exercises the real CI deploy path): set the
   `CIVO_KUBECONFIG` GitHub secret (`base64 < ~/.kube/civo-checktick.yaml
   | gh secret set CIVO_KUBECONFIG` — the only deploy secret still missing),
   then dispatch "Deploy (Civo)" with `image-tag: 0.24.0`: predeploy Job
   pinned to the tag → `set image` → readiness-gated rollout → smoke check
   → auto-rollback on failure. This also pins web off `latest`.
3. **SNOMED**: dispatch "Build SNOMED DB" (works now: `--no-seed` is in the
   published image and TRUD/S3 secrets are set), then
   `kubectl create job --from=cronjob/import-snomed-db snomed-import -n checktick`
   → `/healthz` goes `snomed: ok`, `status: ok`.
4. **Resend confirmation emails** for the two test accounts (Graph works,
   SITE_URL points at staging) → click the links → then the runbook Phase 1
   round-trip: log in, create a test survey, submit a response, view/decrypt.
5. Verify which redirect URIs in the Google/Azure app registrations matched
   for staging OIDC (signup worked — record the exact entries).
6. POC exit criteria left: `kubectl apply -k k8s/` idempotency check (re-apply
   the ALLOWED_HOSTS patch after) and the tear-down/re-apply test.
7. Runbook Phase 3 rehearsal planning (Vault storage-migration drill, DB
   restore drill, timing table).

## Pointers

- Runbook + findings ledger: `docs/migration-northflank-to-civo.md`
- Walkthrough + validation commands: `k8s/README.md`
- Deploy workflow: `.github/workflows/deploy-civo.yml` — needs
  `CIVO_KUBECONFIG` GitHub secret (still to set)
- SNOMED build workflow: `.github/workflows/build-snomed-db.yml` — GitHub
  secrets `TRUD_API_KEY`, `CIVO_S3_ACCESS_KEY`, `CIVO_S3_SECRET_KEY` are set
