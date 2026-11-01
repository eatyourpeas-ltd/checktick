# POC Status — Civo Migration (session handoff)

Working state of the `civo-migration` branch POC. Read this together with
`docs/migration-northflank-to-civo.md` (the runbook — its Phase 0 "findings"
ledger records every environment discovery so far) and `k8s/README.md`.

Last updated: 2026-11-01 (end of session 2).

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
- Structural config (`checktick-config`) + local overlay
  (`checktick-config-local`) + `checktick-secrets` all applied.
- `/healthz` serving: HTTP 200 via pod localhost AND the Service DNS —
  `db: ok`, `vault: ok`, `snomed: unavailable`, `status: degraded`
  (SNOMED absent until the CI build runs — see next steps).
- Zero-downtime proof: **PASSED** — the `zdt-test` curl loop pod (1 req/s
  against the Service DNS) ran through TWO full `rollout restart`s of
  `deploy/checktick-web`: zero FAILs.
- Ingress: Traefik (hostNetwork DaemonSet, ports 80/443 on the node external
  IP) routes `staging.checktick.uk` → `checktick-web`; verified 200
  `/healthz` via the node IP with a Host header, over both HTTP and HTTPS.
  cert-manager `ClusterIssuer` (letsencrypt-production) + `IngressClass` +
  Ingress applied; the Certificate's HTTP-01 challenge is pending DNS.
- CronJobs: all 13 applied (incl. the new `import-snomed-db`);
  `process-recovery-time-delays` verified running to completion.

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
- Ingress TLS is waiting on the user's DNS record (next steps). Until it
  exists, https://staging.checktick.uk serves Traefik's default cert.
- POC-only Deployment patch: the staging hostname was appended to the web
  Deployment's `ALLOWED_HOSTS` env via `k8s/scratch-allowhosts-patch.yaml`
  (git-ignored). Any `kubectl apply -f k8s/web.yaml` (or `-k k8s/`) resets
  it — re-apply the patch afterwards. Proper fix is `ALLOWED_HOSTS_EXTRA`
  in settings.py (runbook Phase 6 backlog; noted in `k8s/web.yaml`).
- The `zdt-test` pod is still running (1 req/s loop) — delete it when done
  with the POC.

## Next steps (next session)

1. DNS: create an A record `staging.checktick.uk` → `74.220.17.170` (the
   node external IP Traefik answers on; re-check with
   `kubectl get nodes -o wide`). cert-manager then completes the HTTP-01
   challenge — verify `kubectl -n checktick get certificate` shows READY
   True and `https://staging.checktick.uk/healthz` returns 200.
2. SNOMED CI build: set the GitHub secrets `TRUD_API_KEY`,
   `CIVO_S3_ACCESS_KEY`, `CIVO_S3_SECRET_KEY` (see
   `.github/workflows/build-snomed-db.yml` header), dispatch the "Build
   SNOMED DB" workflow, then run the in-cluster import:
   `kubectl create job --from=cronjob/import-snomed-db snomed-import -n checktick`.
   Expect `/healthz` → `snomed: ok`, `status: ok`.
3. Runbook Phase 1 round-trip through the ingress: log in, create a test
   survey, submit a response, view/decrypt it (proves DB + Vault + key
   hierarchy together).
4. POC exit criteria left: `kubectl apply -k k8s/` idempotency check (no
   spurious restarts) and the tear-down/re-apply test.
5. Runbook Phase 3 rehearsal planning (Vault storage-migration drill, DB
   restore drill, timing table).

## Pointers

- Runbook + findings ledger: `docs/migration-northflank-to-civo.md`
- Walkthrough + validation commands: `k8s/README.md`
- Deploy workflow (manual dispatch, not yet used): `.github/workflows/deploy-civo.yml`
  — needs `CIVO_KUBECONFIG` GitHub secret (`base64 < ~/.kube/civo-checktick.yaml
  | gh secret set CIVO_KUBECONFIG`)
- SNOMED build workflow: `.github/workflows/build-snomed-db.yml` — needs
  `TRUD_API_KEY`, `CIVO_S3_ACCESS_KEY`, `CIVO_S3_SECRET_KEY` GitHub secrets
