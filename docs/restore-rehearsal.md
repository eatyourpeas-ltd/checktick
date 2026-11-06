---
title: Quarterly Restore Rehearsal
category: development
priority: 14
---

# Quarterly Restore Rehearsal

Step-by-step procedure for the quarterly proof that production backups are
actually restorable. Required by the
[Backup & Data Retention Policy](compliance/backup-policy.md) §5 (quarterly —
January, April, July, October); results are recorded in
[`docs/compliance/restoration-test-log.md`](compliance/restoration-test-log.md)
as DSPT/BCDR evidence.

The rehearsal restores the **latest nightly base backup + WAL chain from Civo
Object Store** into a throwaway CloudNativePG cluster, then proves the result
is complete and usable. It is read-only for production: no writes to the
database, no writes to the object store, no row contents ever leave the
database — **counts only**.

`s/k8s-restore-rehearsal` executes this entire procedure step by step; this
page is the reference explanation of what it does and why.

## What the drill proves

1. **Restorability** — the latest base backup + WAL archive produce a working
   PostgreSQL 17 cluster
2. **Integrity** — every public table matches production exactly, by name and
   exact row count
3. **Schema currency** — `manage.py migrate --check` reports no pending
   migrations against the restored copy

## Safety rules

- The scratch cluster has **no backup/barman configuration** — a restored copy
  of production data must never be re-archived (data minimisation).
- Compare **counts only, never row contents**.
- Scratch resources use a `scratch-restore-drill` prefix and are torn down the
  same day.
- Run during a low-traffic window; the drill only reads production.

## Step 1 — Preflight: verify the backup chain is healthy

Run the four backup-verification checks in
[Civo Kubernetes Operations](civo-kubernetes-operations.md#cnpg-postgresql-operations)
(schedule armed, no stuck non-terminal `Backup` objects, no dead pod IP in the
scheduled backup's status, `ContinuousArchiving=True`). Then note the newest
completed backup for the log:

```bash
kubectl get backups -n checktick | sort
```

## Step 2 — Create the scratch cluster from the backup

CNPG restores by pointing a new `Cluster` at the backup object store via
`bootstrap.recovery`. Mirror the production `barmanObjectStore` block
(`k8s/postgres-cnpg.yaml`) — same destination, endpoint and credentials — with
**no backup section of its own**:

```yaml
# scratch-restore-drill.yaml — throwaway restore target. NEVER add a backup:
# section here: a restored copy of production must not be re-archived.
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: scratch-restore-drill
  namespace: checktick
spec:
  instances: 1  # no HA needed for a drill
  imageName: ghcr.io/cloudnative-pg/postgresql:17
  bootstrap:
    recovery:
      # No recoveryTarget = replay WAL to the latest available point.
      backup:
        barmanObjectStore:
          destinationPath: s3://checktick-backups/db
          endpointURL: https://objectstore.lon1.civo.com
          s3Credentials:
            accessKeyId:
              name: checktick-db-backup-creds
              key: ACCESS_KEY_ID
            secretAccessKey:
              name: checktick-db-backup-creds
              key: SECRET_ACCESS_KEY
            region:
              name: checktick-db-backup-creds
              key: REGION
          wal:
            compression: gzip
  storage:
    size: 10Gi
  resources:
    requests:
      cpu: 250m
      memory: 1Gi
    limits:
      memory: 2Gi
```

```bash
kubectl apply -f scratch-restore-drill.yaml
```

Notes from the migration drills that still apply:

- The PVC is `WaitForFirstConsumer` — it stays `Pending` until the pod starts.
  Never wait for `Bound` first.
- CNPG downloads the base backup then replays WAL; expect several minutes
  before the cluster reports `healthy`:

```bash
kubectl get cluster scratch-restore-drill -n checktick -w
# wait for PHASE: healthy
```

The restored copy is reached with the **production owner credentials**
(`checktick-db-creds`): a physical base backup carries the source's
authentication verbatim, so the production `checktick` user's password works
on the copy. The production cluster uses an external owner secret, so CNPG
generates no `-app` secret for it — this is why the drills below consume
`checktick-db-creds` via `PG*` environment variables (which also avoids any
URL-escaping issues).

## Step 3 — Exact-count verification

Run a helper pod holding the production URI (the application's own
`DATABASE_URL` from `checktick-secrets`) and the restored copy's credentials
(`PG*` env from `checktick-db-creds`), then generate per-table counts on
both sides (counts only):

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: scratch-restore-counts
  namespace: checktick
spec:
  restartPolicy: Never
  containers:
    - name: counts
      image: postgres:17-alpine
      command: ["sleep", "3600"]
      env:
        # Production: the application's own connection string.
        - name: PROD_DB_URL
          valueFrom: {secretKeyRef: {name: checktick-secrets, key: DATABASE_URL}}
        # Restored copy: production owner credentials (the physical backup
        # carries the source's auth verbatim), consumed as psql PG* vars.
        - name: PGHOST
          value: scratch-restore-drill-rw
        - name: PGDATABASE
          value: checktick
        - name: PGUSER
          valueFrom: {secretKeyRef: {name: checktick-db-creds, key: username}}
        - name: PGPASSWORD
          valueFrom: {secretKeyRef: {name: checktick-db-creds, key: password}}
```

```bash
kubectl apply -f scratch-restore-counts.yaml
kubectl wait --for=condition=Ready pod/scratch-restore-counts -n checktick --timeout=180s

# Generate one SELECT COUNT(*) per public table, then run it — both sides.
# (Two-step so all quoting happens inside the pod; URLs never appear in args.)
printf '%s\n' \
  "psql \"\$PROD_DB_URL\" -Atc \"SELECT 'SELECT ' || quote_literal(tablename) || ' AS tbl, COUNT(*) FROM ' || quote_ident(tablename) || ';' FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename\" > /tmp/c.sql" \
  "psql \"\$PROD_DB_URL\" -Atf /tmp/c.sql" \
  | kubectl exec -i -n checktick scratch-restore-counts -- sh -s > counts-prod.txt

printf '%s\n' \
  "psql -Atc \"SELECT 'SELECT ' || quote_literal(tablename) || ' AS tbl, COUNT(*) FROM ' || quote_ident(tablename) || ';' FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename\" > /tmp/c.sql" \
  "psql -Atf /tmp/c.sql" \
  | kubectl exec -i -n checktick scratch-restore-counts -- sh -s > counts-drill.txt

diff -u counts-prod.txt counts-drill.txt && echo "COUNTS MATCH — drill PASSES"
```

A non-empty diff is a drill FAILURE: do not tear down, investigate immediately
(the restoration-test-log entry should record the discrepancy either way).

## Step 4 — Schema currency (`migrate --check`)

Run the application's migration check against the restored copy, using the
same live pinned release image as production. `DATABASE_URL` is constructed
in-container from the owner credentials with `quote_plus` (URL-safe), and
`env` entries win over `envFrom` so the check targets the drill cluster:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: scratch-restore-mcheck
  namespace: checktick
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: check
          image: ghcr.io/eatyourpeas-ltd/checktick:<current pinned release tag>
          command:
            - sh
            - -c
            - |
              export DATABASE_URL="$(python -c 'import os
              from urllib.parse import quote_plus
              print("postgresql://checktick:" + quote_plus(os.environ["PGPASSWORD"]) + "@scratch-restore-drill-rw:5432/checktick")')"
              exec python manage.py migrate --check
          envFrom:
            - configMapRef: {name: checktick-config}
            - configMapRef: {name: checktick-config-local}
            - secretRef: {name: checktick-secrets}
          env:
            - name: PGPASSWORD
              valueFrom: {secretKeyRef: {name: checktick-db-creds, key: password}}
```

```bash
kubectl apply -f scratch-restore-mcheck.yaml
kubectl wait --for=condition=complete job/scratch-restore-mcheck -n checktick --timeout=300s \
  && kubectl logs job/scratch-restore-mcheck -n checktick | tail -3
```

## Step 5 — Record the drill

Append an entry to
[`docs/compliance/restoration-test-log.md`](compliance/restoration-test-log.md):
date, the base backup used (name/timestamp from Step 1), restore + verification
timings, tables compared, counts result, `migrate --check` result, performed by
(CTO) and verified by (SIRO).

## Step 6 — Teardown (same day)

```bash
kubectl delete job scratch-restore-mcheck -n checktick --ignore-not-found
kubectl delete pod  scratch-restore-counts -n checktick --ignore-not-found
kubectl delete cluster scratch-restore-drill -n checktick
# The cluster finalizer removes its instance PVCs; verify and clean up any
# leftovers (e.g. scratch-restore-drill-1):
kubectl get pvc -n checktick | grep scratch
kubectl delete pvc scratch-restore-drill-1 -n checktick --ignore-not-found
rm -f counts-prod.txt counts-drill.txt scratch-restore-*.yaml
```

## Vault-side note

This drill covers the database only. Vault storage backup is a separate,
ceremony-gated procedure today (see
[Civo Kubernetes Operations](civo-kubernetes-operations.md#vault-operations));
once the Raft migration + nightly `raft snapshot save` CronJob land
(hardening backlog #1), add a Vault snapshot-restore test to this rehearsal —
it becomes fast and unseal-ceremony-free at that point.

## Related

- [Civo Kubernetes Operations](civo-kubernetes-operations.md) — backup verification checks and restore context
- [Backup & Data Retention Policy](compliance/backup-policy.md) — the quarterly requirement (§5)
- [Restoration Test Log](compliance/restoration-test-log.md) — where results are recorded
- [`k8s/postgres-cnpg.yaml`](../k8s/postgres-cnpg.yaml) — the production cluster and object-store configuration
