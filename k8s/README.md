# CheckTick Kubernetes Manifests

Generic, public manifests for running CheckTick on Kubernetes — used for the
Civo (London) deployment and reusable by any cluster with a default
StorageClass supporting `ReadWriteMany` volumes (Longhorn on Civo) and the
Traefik ingress controller. Self-hosters do **not** need Kubernetes: the
supported default path remains
[docker-compose.registry.yml](../docker-compose.registry.yml) and the
[self-hosting docs](../docs/self-hosting.md). This directory is the optional
"advanced" path (see [docs/vault.md](../docs/vault.md), Option 3).

These manifests contain **no secrets and no hostnames**. Environment-specific
values are applied out-of-band.

| File | Contents |
| :--- | :--- |
| `namespace.yaml` | `checktick` namespace |
| `web-configmap.yaml` | Non-sensitive config (hostnames, Vault addr, defaults) |
| `vault.yaml` | Vault StatefulSet (integrated Raft storage, manual unseal), Service, airgap NetworkPolicy |
| `vault-snapshot.yaml` | Nightly ENCRYPTED Vault snapshot CronJob — deliberately NOT in kustomization.yaml (out-of-band prerequisites: AppRole ceremony + operator age key; see the file header) |
| `web.yaml` | Web Deployment (probes, rolling update, anti-affinity), Service, PVCs, PDB |
| `migrate-job.yaml` | Pre-deploy Job: migrations + idempotent syncs |
| `cronjobs.yaml` | All 13 scheduled tasks (docs/self-hosting-scheduled-tasks.md); SNOMED arrives as a small object-store import — the 8 GiB in-cluster build is replaced by the CI workflow |
| `ingress.yaml` | TEMPLATE for the Traefik Ingress + cert-manager TLS + IngressClass — copy to the git-ignored `ingress.local.yaml` and set your hostname |
| `secrets.example.env` | Template for the Secret (copy to `secrets.env`, git-ignored) |
| `config.example.env` | Template for the local config overlay (copy to `config.env`, git-ignored) |
| `postgres-cnpg.yaml` | **Optional** in-cluster PostgreSQL 17 (CloudNativePG) — budget path |
| `postgres-networkpolicy.yaml` | `checktick-db-ingress` NetworkPolicy — DB reachable on 5432/8000 only by web pods, the batch CronJobs (label grant), the CNPG operator and the cluster's own instances |
| `staging-postgres-cnpg.yaml` | **Optional** staging PostgreSQL (CloudNativePG) — trimmed clone of `postgres-cnpg.yaml`: 1 instance, no backups, no WAL archiving + its own DB-ingress NetworkPolicy |
| `staging-web.yaml` | **Optional** staging web Deployment (1 replica) + Service — same namespace and PVCs as prod, `DATABASE_URL` from the `STAGING_DATABASE_URL` secret key |
| `staging-migrate-job.yaml` | Staging pre-deploy Job (migrations + idempotent syncs against the staging DB) — run once per staging release |
| `staging-cronjobs.yaml` | Staging scheduled tasks — exactly ONE CronJob (`prune-unconfirmed-users-staging`); everything else is prod-only |
| `openobserve.yaml` | Self-hosted OpenObserve log store — ClusterIP-only (port-forward 5080), single replica on a Longhorn PVC; the retention layer for the stdout JSON ([Infrastructure Logging](../docs/infrastructure-logging.md)) |
| `openobserve.example.env` | Template for the `openobserve-auth` Secret (copy to git-ignored `k8s/openobserve.env`) — shared by the OpenObserve root user and collector Basic auth |
| `log-collector.yaml` | Fluent Bit DaemonSet → OpenObserve stream `default/default` (one timeline with the NF-era archive). **Deliberately NOT in kustomization.yaml** — one fluent-bit per node tipped a node over its memory wall (2026-11-05); apply out-of-band only after the node-pool resize + headroom go/no-go ([Civo ops → Node Pool Resize](../docs/civo-kubernetes-operations.md)) |
| `longhorn-backup.yaml` | Nightly off-cluster Longhorn volume backups (`openobserve-data`, `checktick-media`) to the Civo object store — out-of-band like `postgres-cnpg.yaml` (hardening-backlog item 6) |
| `smoke-test.py` | Post-deploy smoke gate (19 checks incl. the encrypt/decrypt round-trip) |

## Database options

These manifests are database-agnostic — the app only reads `DATABASE_URL`
from the Secret.

- **Civo managed PostgreSQL 17** (default; ~$43/mo entry tier): least
  operational burden — backups, upgrades, failover are the provider's job.
- **In-cluster CloudNativePG** (`postgres-cnpg.yaml`, optional): near-zero
  marginal cost on existing nodes, operator-managed failover, scheduled
  backups + WAL archiving to Civo Object Storage (point-in-time recovery).
  You operate Postgres. Requires the CNPG operator first, which is why the
  file is intentionally excluded from `kustomization.yaml`.

Either way the 16 → 17 major upgrade happens during the cutover
`pg_dump`/`pg_restore` (dump with the target's binaries — never the
reverse).

## Secrets

```bash
cp k8s/secrets.example.env k8s/secrets.env   # fill in real values
kubectl create secret generic checktick-secrets -n checktick \
  --from-env-file=k8s/secrets.env
# subsequent updates:
kubectl create secret generic checktick-secrets -n checktick \
  --from-env-file=k8s/secrets.env --dry-run=client -o yaml | kubectl apply -f -
```

`k8s/secrets.env` is git-ignored. Never commit credentials: this repository is
public and the docs ship inside the container image. Long-term, prefer SOPS in
a private ops repo. `PLATFORM_CUSTODIAN_COMPONENT` must never appear in any
environment (settings.py hard-fails; docs/vault.md control F6).

## Local config overlay (config.env)

Environment-identifying config — real domains, branding, compliance
contacts, company details, feature URLs — stays out of the public repo. It
lives in a second git-ignored file, `k8s/config.env` (template:
`k8s/config.example.env`), applied as the `checktick-config-local` ConfigMap:

```bash
cp k8s/config.example.env k8s/config.env
kubectl create configmap checktick-config-local -n checktick \
  --from-env-file=k8s/config.env --dry-run=client -o yaml | kubectl apply -f -
```

Rules: no quoting (kubectl stores values raw), and DELETE lines you don't
want set — a blank `KEY=` overrides the default with an empty string.
Precedence is the `envFrom` order in every workload: `checktick-config`
(structural defaults, committed) → `checktick-config-local` (this overlay)
→ `checktick-secrets`. The overlay ConfigMap must exist before web pods
start (they reference it via `envFrom`), so create it even if nearly empty
during early POC steps.

## Local kubectl setup (during the migration)

Keep cluster configs in **separate files** while production is split across
providers — the classic kubectl failure mode is applying to the wrong
cluster after a forgotten context switch:

```bash
civo k8s config <cluster-name> > ~/.kube/civo-checktick.yaml
chmod 600 ~/.kube/civo-checktick.yaml

export KUBECONFIG=~/.kube/civo-checktick.yaml   # per Civo working session
kubectl config current-context                   # glance before any apply/delete
```

Any other cluster config (e.g. a previous platform's `~/.kube/config`) stays
untouched; a fresh terminal without the export falls back to it. After the
migration completes (runbook Phase 6), consolidate at will. The deploy
workflow's kubeconfig is separate again — a base64-encoded GitHub secret
(see [deploy-civo.yml](../.github/workflows/deploy-civo.yml)).

## POC walkthrough (throwaway Vault + synthetic data)

Applies to a fresh Civo cluster (3 nodes, London). For a production migration
the Vault step differs critically: restore the existing storage and unseal
with the EXISTING shares — **never** `vault operator init` (a fresh init
makes every encrypted survey permanently undecryptable).

```bash
# 0. Prereqs: cluster with Longhorn + Traefik, cert-manager installed,
#    a ClusterIssuer, and a reachable managed PostgreSQL 16.
#    Set the real hostname in web-configmap.yaml + ingress.yaml first.

# 1. Namespace + config + Vault (not the web Deployment yet)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/web-configmap.yaml
kubectl apply -f k8s/vault.yaml

# 2. Initialise the THROWAWAY Vault and configure AppRole per
#    docs/vault.md (shares are disposable in the POC; use the real
#    4-share/3-threshold shape to rehearse the ceremony)
kubectl exec -n checktick vault-0 -it -- vault operator init -key-shares=4 -key-threshold=3
kubectl exec -n checktick vault-0 -it -- vault operator unseal   # x3
# ... enable kv, create policy + AppRole per docs/vault.md ...
# then put role_id/secret_id into k8s/secrets.env and create the Secret (above)

# 3. Pre-deploy Job (migrations + syncs) — POC first boot also needs the
#    external datasets seeded; run it once from the same job manually if
#    not yet done:
kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/checktick-predeploy -n checktick --timeout=300s

# 4. SNOMED CT: dispatch the "Build SNOMED DB" GitHub workflow once
#    (.github/workflows/build-snomed-db.yml — needs the TRUD_API_KEY,
#    CIVO_S3_ACCESS_KEY and CIVO_S3_SECRET_KEY GitHub secrets). It builds
#    snomed.db on a free 16 GB runner and uploads it to the object store;
#    then import it in-cluster (weekly CronJob, manual first run):
kubectl create job --from=cronjob/import-snomed-db snomed-import -n checktick
kubectl wait --for=condition=complete job/snomed-import -n checktick --timeout=1h

# 5. Web + ingress (ingress.yaml is a template: copy to the git-ignored
#    k8s/ingress.local.yaml, set your hostname, apply that)
kubectl apply -f k8s/web.yaml
cp k8s/ingress.yaml k8s/ingress.local.yaml   # edit the hostname first
kubectl apply -f k8s/ingress.local.yaml
kubectl rollout status deployment/checktick-web -n checktick

# 6. Scheduled tasks (enable once stable)
kubectl apply -f k8s/cronjobs.yaml
```

## POC validation (exit criteria)

1. `/healthz` returns `status: ok` — DB, Vault unsealed, SNOMED present:

   ```bash
   kubectl exec -n checktick deploy/checktick-web -- curl -sf localhost:8000/healthz
   ```

2. Log in through the ingress; create a survey, submit a response, view it —
   the encrypt/decrypt round-trip proves DB + Vault + key hierarchy together.
3. **Zero-downtime proof** — run against the ingress while rolling a new tag:

   ```bash
   while true; do curl -sf https://HOST/healthz >/dev/null || echo FAIL; sleep 1; done
   kubectl set image -n checktick deploy/checktick-web web=ghcr.io/eatyourpeas-ltd/checktick:NEWTAG
   # expect zero FAILs
   ```

4. `kubectl apply -k k8s/` is idempotent — no spurious pod restarts.

## Design notes

- **Probes**: readiness is the deep `/healthz` (DB + Vault sealed + SNOMED);
  liveness is the trivial `/api/health`. Liveness must never point at
  `/healthz` — a sealed Vault would trigger restart loops, and restarts cannot
  fix a seal; the unseal ceremony can.
- **Migrations** never run at container start (image CMD is gunicorn-only).
  Apply `migrate-job.yaml` before each deploy. Keep migrations
  expansion/contract: old and new pods run concurrently during a rollout.
- **Media** is a Longhorn RWX PVC (admin-uploaded icons; RWX because the surge
  pod mounts it during rollouts). An initContainer chowns it on boot because
  Longhorn RWX (NFS-backed) does not honour fsGroup.
- **SNOMED** lives on an RWX PVC but is never opened from the share: each pod
  copies `snomed.db` to a node-local `emptyDir` at startup, so SQLite is never
  touched over NFS. The file is built by CI
  ([build-snomed-db.yml](../.github/workflows/build-snomed-db.yml) — the
  sct ndjson step peaks above 4 GiB and cannot run on 4 GB nodes) and the
  importer CronJob swaps it in with an atomic rename; the seed runs
  in-cluster where the database lives.
- **Vault** runs integrated Raft storage (migrated from file storage
  2026-11-06) with manual unseal behind a NetworkPolicy that denies all
  egress except its own cluster port (8201) and accepts ingress from web
  pods and the nightly snapshot CronJob on 8200. There is
  deliberately no liveness probe. A node drain re-seals Vault and 503s the
  app until the ceremony — pin Vault's node and drain it manually, or move
  Vault to a dedicated small cluster (hardening backlog — see
  docs/civo-kubernetes-operations.md).
- **Rolling updates**: `maxUnavailable: 0`, `maxSurge: 1`, anti-affinity across
  nodes, PDB `minAvailable: 1`, `preStop` sleep 10s for endpoint convergence.

## Production deploy flow

The manifests pin released image tags — never `latest` — in `web.yaml` (web
+ initContainers), `migrate-job.yaml`, and `cronjobs.yaml`. Bump the pinned
tags in the release PR so `kubectl apply -k k8s/` cannot regress the live
deployment to an older image.

CI deploys additionally run `kubectl set image` over **every CronJob in the
namespace** after the smoke check. CronJobs are not part of the Deployment
rollout and would otherwise keep their manifest pin indefinitely — before
this they sat on `0.24.2` while the web Deployment was rolled to `0.25.x`
(found 2026-11-07). The manifest pins remain the bootstrap default for a
fresh `kubectl apply -k k8s/` and a manual-apply safety net.

1. `kubectl apply -f k8s/migrate-job.yaml` → wait for completion
2. `kubectl set image -n checktick deploy/checktick-web web=ghcr.io/eatyourpeas-ltd/checktick:X.Y.Z`
   (pin released version tags — docs/versioning-and-deployment.md)
3. `kubectl rollout status deployment/checktick-web -n checktick`
4. Roll back with `kubectl rollout undo` if readiness never goes green.

### CI deploys

[`.github/workflows/deploy-civo.yml`](../.github/workflows/deploy-civo.yml)
automates the sequence above with the same zero-downtime semantics:

1. re-runs the pre-deploy Job pinned to the same tag
2. `kubectl set image` + `rollout status` (readiness-gated)
3. smoke-checks `/healthz` through the service
4. rolls every prod CronJob in the namespace to the same tag (CronJobs are not
   part of the Deployment rollout — see the note above)
5. auto-rollbacks (`rollout undo`) if anything fails after the image changed
   (the CronJob roll runs after the smoke check, so a failed deploy leaves
   CronJobs on their previous tag)
6. deploys STAGING (separate `deploy-staging` job, `needs: deploy`): the same
   sequence against the staging environment — staging migrate Job, staging
   web rollout, staging smoke check, then the one staging CronJob. A staging
   failure never rolls back prod; with `maxUnavailable: 0` a failed staging
   rollout leaves the previous tag serving.

One-time setup:

```bash
civo k8s config <cluster-name> > /tmp/kubeconfig.yaml   # or download from the Civo dashboard
base64 < /tmp/kubeconfig.yaml | gh secret set CIVO_KUBECONFIG
rm /tmp/kubeconfig.yaml
```

Dispatch it from the Actions tab (the `image-tag` input is required — pass
the released tag, e.g. `0.24.2`). Add protection rules (required reviewers)
to the `civo` GitHub environment to make dispatch a gated production deploy.

On main publishes, `docker-publish.yml` dispatches this workflow with the
newly published image tag (swapped from the previous platform's deployment
webhook at migration close-out — runbook Phase 6).

## Staging environment

A second (staging) app + database pair runs in the **same namespace** as
production — same namespace on purpose: the `checktick-media` /
`checktick-snomed-data` RWX PVCs are namespace-scoped and are deliberately
**shared**, so SNOMED arrives for free with no re-import. Vault is shared
too (same `VAULT_ADDR`, same AppRole). The `staging-*.yaml` manifests are
NOT in `kustomization.yaml` — they have out-of-band prerequisites and are
applied in order:

1. Bootstrap Secret + staging CNPG cluster (operator required, as for
   `postgres-cnpg.yaml`; 1 instance, **no backups / WAL archiving** —
   staging data is disposable) with its own DB-ingress NetworkPolicy:

   ```bash
   openssl rand -hex 24   # -> <staging-db-password>\n   kubectl create secret generic checktick-staging-db-creds -n checktick \
     --from-literal=username=checktick \
     --from-literal=password='<staging-db-password>'
   kubectl apply -f k8s/staging-postgres-cnpg.yaml
   kubectl -n checktick wait --for=condition=ready \
     cluster.postgresql.cnpg.io/checktick-staging-db --timeout=300s
   ```

2. `STAGING_DATABASE_URL` (same password) into `checktick-secrets`, and
   `STAGING_SITE_URL` into the config overlay (`k8s/config.env` →
   `checktick-config-local`) — both git-ignored:

   ```bash
   kubectl patch secret checktick-secrets -n checktick \
     -p '{"stringData":{"STAGING_DATABASE_URL":"postgresql://checktick:<staging-db-password>@checktick-staging-db-rw:5432/checktick"}}'
   kubectl create configmap checktick-config-local -n checktick \
     --from-env-file=k8s/config.env --dry-run=client -o yaml | kubectl apply -f -
   ```

3. `kubectl apply -f k8s/vault.yaml` — the airgap must admit
   `app=checktick-staging-web` (staging shares the Vault).
4. Seed once per release (migrations + idempotent syncs against the staging
   DB; SNOMED needs nothing — shared PVC):

   ```bash
   kubectl delete job checktick-staging-predeploy -n checktick --ignore-not-found
   kubectl apply -f k8s/staging-migrate-job.yaml
   kubectl wait --for=condition=complete \
     job/checktick-staging-predeploy -n checktick --timeout=300s
   ```

5. Web + the ONE staging CronJob:

   ```bash
   kubectl apply -f k8s/staging-web.yaml
   kubectl -n checktick rollout status deploy/checktick-staging-web
   kubectl apply -f k8s/staging-cronjobs.yaml
   ```

6. Route the public staging hostname in the git-ignored
   `k8s/ingress.local.yaml` at service `checktick-staging-web` (the cert
   already exists).

No new credentials are needed for staging — the OIDC client IDs/secrets,
  hCaptcha, Vault AppRole and `SECRET_KEY` are all shared via
  `checktick-config-local` + `checktick-secrets`. Console-side, beyond the
  M365/Google redirect URIs (`https://staging.checktick.uk/oidc/callback/`),
  only the hCaptcha sitekey's hostname list (sitekeys are hostname-bound).
  Billing selects the GoCardless API by `ENVIRONMENT` — only `production`
  uses the live API; development AND staging use the sandbox (settings.py —
  shipped in 0.27.1, verified live: staging resolves
  `PAYMENT_ENVIRONMENT: sandbox`). Staging logs are deliberately
  NOT shipped to OpenObserve — the log-collector excludes every `*staging*`
  container log so the prod stream stays unmixed; view them with
  `kubectl logs` (see docs/civo-kubernetes-operations.md → Staging
  environment → Logs). The app derives the OIDC redirect
  base from `SITE_URL`/`STAGING_SITE_URL` (settings.py — shipped in 0.27.1,
  verified live: staging sends `https://staging.checktick.uk/oidc/callback/`).

Staging deploys are automated: the Deploy (Civo) workflow's `deploy-staging`
job (`needs: deploy`) runs the staging migrate Job, rolls
`deploy/checktick-staging-web`, smoke-checks it, then re-images
`prune-unconfirmed-users-staging` (the prod job's CronJob roll skips it, so
the cron only moves once the staging schema is migrated). A staging failure
never rolls back prod; with `maxUnavailable: 0` a failed staging rollout
leaves the previous tag serving. Manual `kubectl set image` (after re-running
`k8s/staging-migrate-job.yaml` at the same tag) remains the fallback.
Capacity (2026-11-08, 2× `g4s.kube.large`): staging adds ~600 Mi steady /
1.5 GiB requests against ~2–2.8 GiB actually free per node — comfortable.
