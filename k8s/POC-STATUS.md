# POC Status — Civo Migration (session handoff)

Working state of the `civo-migration` branch POC. Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — its Phase 0 "findings"
ledger records every environment discovery so far) and `k8s/README.md`.

Last updated: 2026-11-01 (session 2: web serving verified).

## Environment

- Civo Kubernetes `checktick` cluster, LON1, 3 × medium nodes (2 vCPU/4 GB),
  Kubernetes 1.35.0
- Local kubectl via `~/.kube/civo-checktick.yaml` (exported in `~/.zshrc`)
- CNPG operator v1.30.1; cert-manager installed; Longhorn v1.13.0 installed
- Object store: `checktick-backups` (objectstore.lon1.civo.com), credential
  "backups" attached
- Local (git-ignored) files that carry the environment:
  `k8s/secrets.env`, `k8s/config.env`, and the DB password in a password
  manager (also in `checktick-db-creds`)

## What is live and verified

- Vault: single node, initialised (throwaway 4/3 Shamir), unsealed, AppRole
  configured via `vault/setup_vault.py`; `vault-0` 1/1. Root token revoked.
  Manifest fixes (all POC findings, commented in `vault.yaml`): `fsGroup`,
  `disable_mlock`, direct `command:` invocation.
- PostgreSQL 17 (CNPG): 2 instances healthy, WAL archiving verified end to
  end to `s3://checktick-backups/db` (requires the SigV4 `region` SecretKeySelector
  and the S3 checksum env vars — see Cluster spec.env). Nightly base backup
  02:00 UTC. DB password: 48-byte hex; `DATABASE_URL` = 102 bytes.
- Migrate job (`checktick-predeploy`): **passed** — full credential chain
  Django → Secret → service → CNPG verified; migrations and syncs complete.
- Web Deployment: 2 replicas, Longhorn RWX PVCs bound (media + SNOMED share).
- `/healthz` serving: HTTP 200 via pod localhost AND the Service DNS —
  `db: ok`, `vault: ok`, `snomed: unavailable`, `status: degraded`
  (SNOMED absent by design until its CI build exists).
- Structural config (`checktick-config`) + local overlay
  (`checktick-config-local`) + `checktick-secrets` all applied.

## Known state at session close

- **Config overlay precedence finding (session 2):** setting
  `SECURE_SSL_REDIRECT=False` in `web-configmap.yaml` was NOT enough — the
  git-ignored local overlay (`checktick-config-local`, from `k8s/config.env`)
  still carried `SECURE_SSL_REDIRECT=True` and won the envFrom precedence
  chain, so pods kept 301-ing every plain-HTTP request to https. Confusing
  symptom: kubelet startup-probe events showed
  `Get "https://<pod-ip>:8000/healthz"` timeouts even though the probe
  scheme was HTTP — the probe follows the 301, then the TLS handshake
  against plain-HTTP gunicorn hangs. Fix was to delete the key from
  `k8s/config.env`, re-apply the overlay ConfigMap, and `rollout restart`.
  Rule: when changing any posture key, grep BOTH `web-configmap.yaml` and
  `config.env` — the overlay silently overrides the structural default.
- Zero-downtime proof: **PASSED** (session 2) — fresh `zdt-test` curl loop
  pod (1 req/s against the Service DNS) ran through a full
  `rollout restart` of `deploy/checktick-web`: zero FAILs. The `zdt-test`
  pod is still running; delete it when done with the POC.

## Next steps (next session)

1. Run the zero-downtime proof (healthz verification is done — see above).
2. Commit the working tree (`s/lint` first) — it contains the local config
   overlay system, Longhorn storage classes, the ALLOWED_HOSTS probe fix,
   the TLS posture change, and the runbook findings ledger.
3. SNOMED CI build workflow (GitHub Actions, free 16 GB runners; upload to
   `s3://checktick-backups/snomed` with the checksum env vars; small
   in-cluster import job replaces the 8 GiB `update-snomed-db` CronJob).
4. Ingress + TLS on a STAGING hostname (never `checktick.uk` — that DNS
   flip is the final gate of the cutover window, runbook Phase 4 step 10).
5. CronJobs (`k8s/cronjobs.yaml`) once stable; then runbook Phase 3
   rehearsal planning (Vault storage-migration drill, DB restore drill,
   timing table).

## Pointers

- Runbook + findings ledger: `docs/migration-northflank-to-civo.md`
- Walkthrough + validation commands: `k8s/README.md`
- Deploy workflow (manual dispatch, not yet used): `.github/workflows/deploy-civo.yml`
  — needs `CIVO_KUBECONFIG` GitHub secret (`base64 < ~/.kube/civo-checktick.yaml
  | gh secret set CIVO_KUBECONFIG`)
