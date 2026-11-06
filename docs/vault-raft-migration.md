---
title: Vault Raft Migration & Nightly Snapshots (runbook)
category: development
priority: 13
---

# Vault: file storage → integrated Raft + nightly snapshot CronJob

**STATUS: WINDOW EXECUTED + SNAPSHOT PIPELINE LIVE (2026-11-06, session 14).
The Vault is on integrated Raft storage (migrated 17:48–18:03 UTC, ~15 min
sealed window, smoke 19/19) and the nightly ENCRYPTED snapshot CronJob is
applied and first-run verified end-to-end — the age-encrypted object is
confirmed in `s3://checktick-backups/vault/` and the airgap is
negative-tested. REMAINING: the healthchecks.io wiring (operator), the
restore test (closes this runbook), then the post-pass cleanup (delete the
old file data at the volume root, retire the interim tarball note, mark
hardening item 1 done). Three found-live corrections from the execution
are recorded in "Verification notes" — read them before reusing any of
this on another Vault.**

This is hardening item 1 (`docs/civo-kubernetes-operations.md`): the Vault
is the last component with no scheduled backup. File storage has no online
snapshot path; a nightly stop-copy is NOT acceptable (it would put unseal
shares on a scheduled job — breaks the custody model). Integrated Raft
storage supports `vault operator raft snapshot save` while unsealed — no
ceremony, no shares on the cron.

## Verification notes (2026-11-06, Vault 1.21 docs)

- **`vault operator migrate`** —
  developer.hashicorp.com/vault/docs/commands/operator/migrate:
  - config stanzas are **`storage_source` / `storage_destination`** — NOT
    `storage` / `destination`. The pre-session draft had the wrong names
    and the migrate would have failed mid-window.
  - offline operation: Vault refuses to start while a migration lock is
    present; a stale lock clears with `-reset`.
  - resumable: `-start <key-prefix>` continues a halted migrate.
  - the destination must NOT be initialised beforehand; the source is left
    untouched except for the lock key → the rollback path holds.
  - **FOUND LIVE (2026-11-06 window)**: the migrate does NOT create the
    destination directory — `mkdir /vault/storage/raft` (empty dir) FIRST,
    else it fails with `failed to open bolt file: open
    /vault/storage/raft/vault.db: no such file or directory`. "Not
    initialised" means no raft data inside it — not a missing dir.
  - after the migrate: reconfigure storage, start, **unseal with the
    EXISTING shares** (a migrated raft dir is NOT a fresh init).
- **`vault operator raft snapshot save|restore|inspect`** —
  developer.hashicorp.com/vault/docs/commands/operator/raft:
  save/restore/inspect are supported on CE when raft is the `storage`
  (NOT for ha_storage-only raft — ours is `storage`). **`restore` returns
  BEFORE the restore completes** — wait for `post-unseal setup complete`
  + `vault is unsealed` in the server log before trusting the drill pod.
- **raft stanza** —
  developer.hashicorp.com/vault/docs/configuration/storage/raft:
  `storage "raft" { path, node_id }` + top-level **`cluster_addr`**
  (required; no `ha_storage` may be declared alongside; recommend
  `disable_mlock = true` — already set). Single node → no `retry_join`.
- **`age`** is packaged in alpine v3.21 community (age 1.2.1-r5) — the
  `alpine:3.21` + `apk add age` encrypt container is viable.
- **Snapshot endpoint (found live at first run, 2026-11-06)**: in 1.21.4
  `vault operator raft snapshot save` calls `GET /v1/sys/storage/raft/snapshot`
  — the CLI docs never state the underlying API path, and the older
  `sys/raft/snapshot/save` path (used by the first policy) 403s. The policy
  grants read+update on `sys/storage/raft/snapshot` only; restore
  (`sys/storage/raft/snapshot-restore`, sudo) is deliberately NOT granted —
  the cron only saves.
- **Airgap consequence (the subtle one)**: with raft storage the node may
  dial its OWN cluster port 8201 via the Service, which the previous
  deny-all egress would have dropped silently → the airgap in
  `k8s/vault.yaml` now also carries a scoped 8201 allow (`app=vault` only),
  committed with this prep.
- **PVC layout (verified live 2026-11-06, pre-window)**: the `data-vault-0`
  volume root IS the file-storage dir — `core/`, `logical/`, `sys/`,
  `audit/`, `auth/` sit directly at the PVC root; there is NO `file/`
  subdir (the draft assumed one). After the remount to `/vault/storage`:
  the migrate source path is **`/vault/storage`**, the rollback stanza is
  `path = "/vault/storage"`, and the post-restore-test cleanup is "delete
  the old file-storage dirs at the volume root (everything except
  `raft/`)" — all three corrected in this runbook today.

## Current state (verified 2026-11-05/06)

- `hashicorp/vault:1.21.4`, StatefulSet `vault`, ns `checktick`, 1 replica
- File storage at `/vault/file`, PVC `data-vault-0` (10 Gi, storageclass
  **civo-volume** — NOT Longhorn, so the Longhorn nightly backup does not
  cover it; that is deliberate, this runbook replaces it). The volume root
  IS the storage dir (verified live 2026-11-06: `core/`, `logical/`, `sys/`
  at the PVC root — no `file/` subdir)
- Seal: Shamir 3-of-4, manual unseal. `s/k8s-vault-unseal`'s stdin piping is
  BROKEN on this kubectl — use the interactive fallback:
  `kubectl -n checktick exec -it vault-0 -- vault operator unseal`
- `disable_mlock=true`, `tls_disable=1` (in-cluster plain HTTP; TLS is a
  separate backlog item)
- NetworkPolicy `vault-airgap`: ingress on 8200 from `app=checktick-web`
  and (since session 13) the snapshot pods; egress denied except a scoped
  8201 self-allow. The snapshot pod is a SEPARATE pod (not a sidecar on
  vault-0) so the airgap cannot block its S3 egress.
- Storage size: ~388 KB (tiny — the migrate step is seconds, not minutes)
- AppRole `checktick-app` minted on the migrated Vault (cutover T+5); the
  migration carries all policies/roles — no re-mint needed
- Interim backup: manual stop-copy tarball (2026-11-05, sha256 b6b9a9bd…,
  Bitwarden-bound). Keep until a snapshot restore-test passes.

## Design decisions (record, CTO sign-off on #1)

1. **Snapshot storage tier — RESOLVED 2026-11-06 (CTO discussion): the
   snapshot is ENCRYPTED with an operator-held key before upload.** A raw
   raft snapshot is barrier-encrypted (useless without 3-of-4 shares), but
   storing it unencrypted on internet-reachable object storage still widens
   the copy set of crown-jewel material. The CronJob therefore wraps it
   with `age -r <OPERATOR_RECIPIENT>` and uploads only the `.age` blob:
   the stored object is useless without BOTH the Shamir shares AND the
   operator's private key (Bitwarden-held). Destination
   `s3://checktick-backups/vault`, retain 14. The Bitwarden manual copy
   remains the custody-grade offline copy. Rationale for nightly freshness
   at all: the Vault is NOT static — every survey creation writes escrow
   key material, so any point-in-time copy silently rots, and restoring a
   stale one makes post-copy surveys permanently undecryptable (fails
   silently at decrypt time, not at restore time).
2. **Raft path on the SAME PVC.** Re-mount the PVC at `/vault/storage`
   (parent), migrate into `/vault/storage/raft`; the file data IS the
   volume root, so it stays directly under `/vault/storage/` (siblings of
   `raft/`) until a restore-test passes (rollback path).
   The `volumeMounts` edit is mutable on a StatefulSet (only
   `volumeClaimTemplates` are immutable) — no STS recreate needed.
3. **Snapshot auth: dedicated AppRole**, not root. Mint policy
   `vault-snapshot` (`sys/storage/raft/snapshot` only — read+update on that
   single save endpoint; found live at first run 2026-11-06: the 1.21.4 CLI
   calls `GET /v1/sys/storage/raft/snapshot`, not the older
   `sys/raft/snapshot/save` path) + AppRole `vault-snapshot`, credentials in
   a new k8s Secret. Same pattern as `checktick-app`.
4. **Sealed-window behaviour (fixed 2026-11-05):** web startupProbe now
   points at `/api/health`, so a sealed Vault = web pods NotReady (Traefik
   404s, StatusCake fires — expected) but NO restart loop. Keep the window
   tight anyway.

## Pre-flight (before the window) — ALL DONE 2026-11-06

- [x] ~~⚠ VERIFY `vault operator migrate` syntax/semantics~~ **DONE
      (session 13)** — see Verification notes. The stanza-name correction
      is the breaking one: `storage_source` / `storage_destination`.
- [x] Fresh stop-copy taken IN-WINDOW, before the migrate:
      `~/vault-backup-2026-11-06-pre-raft/vault-storage-2026-11-06-pre-raft.tar.gz`
      (29 KB, sha256 `8c8b347f…2acfa`) — Bitwarden custody, then delete
      the local copy.
- [x] Shares to hand — used three times: the post-migrate unseal, the
      ceremony generate-root, and a second generate-root after the
      snapshot-policy fix (Verification notes).
- [x] age keypair generated: recipient live in the `vault-snapshot-config`
      ConfigMap; private key → Bitwarden only.
- [x] Pods quiet — activity check 17:41 UTC: zero authenticated users in
      the app logs (bot noise only; last event 14:47). Traefik access
      logging is OFF (a monitoring gap worth noting).
- [x] StatusCake: fired during the window, recovered after the unseal.

## The window — EXECUTED 2026-11-06 17:48–18:03 UTC (kept as the record)

Actuals: scale 0 at 17:48:47 → helper up → stop-copy → migrate (all keys
< 1 s) → raft ConfigMap + `/vault/storage` remount applied → scale 1 →
operator unseal ~18:03. Web pods NotReady for the window (no restart
loops — the fixed `/api/health` startupProbe held). Post-verify:
`Storage Type raft`, HA active, committed=applied index, `/healthz` fully
ok, **smoke 19/19** (the escrow KV write→read→delete exercises the raft
WRITE path).

1. **Scale to 0**: `kubectl -n checktick scale statefulset vault --replicas=0`
   (web goes NotReady within ~30 s — expected)
2. **Edit `k8s/vault.yaml`**: move the data volumeMount from `/vault/file`
   to `/vault/storage` (parent); apply. (With replicas=0 nothing restarts;
   the file data is the volume root, so it appears directly under
   `/vault/storage` — `core/`, `logical/`, `sys/`.)
3. **Migrate** — the prepared helper (git-ignored scratch, never committed):
   ```
   kubectl apply -f k8s/scratch-vault-raft-migrate.yaml
   kubectl -n checktick exec -it vault-migrate-helper -- \
     vault operator migrate -config=/vault/migrate/migrate.hcl
   kubectl -n checktick delete pod vault-migrate-helper
   ```
   The helper's `migrate.hcl` carries the VERIFIED stanza names:
   ```hcl
   storage_source "file" {
     path = "/vault/storage"
   }
   storage_destination "raft" {
     path    = "/vault/storage/raft"
     node_id = "vault-0"
   }
   cluster_addr = "http://127.0.0.1:8201"
   ```
   388 KB → seconds. If it halts: resume with `-start <key-prefix>`; a
   stale lock blocks the Vault restart and clears with `-reset`. Provide
   unseal shares if prompted (the operator has them to hand).
4. **Reconfigure** `vault.yaml`'s ConfigMap — final storage stanza
   (verified):
   ```hcl
   storage "raft" {
     path    = "/vault/storage/raft"
     node_id = "vault-0"
   }
   cluster_addr = "http://vault.checktick.svc.cluster.local:8201"
   ```
   Keep `ui`, `disable_mlock`, the listener and `api_addr` as they are, and
   update the file's header comment (file → raft). The airgap NetworkPolicy
   in the same file is ALREADY the post-migration form (snapshot-pod ingress
   + the scoped 8201 self-allow — committed in session 13). Apply.
5. **Scale to 1**, wait Running (Sealed), **operator unseals** (interactive
   form: `kubectl -n checktick exec -it vault-0 -- vault operator unseal`).
6. **Verify**: `/healthz` fully ok; `vault status` shows
   `Storage Type raft`; `vault operator raft list-peers` shows `vault-0`
   as leader (proves the 8201 self-allow actually holds — if this hangs,
   the airgap egress is the suspect); AppRole login works (healthz's deep
   check proves it); smoke test 19/19 (`k8s/smoke-test.py` in a web pod,
   the session-4 pattern).
7. **Do NOT delete the old file-storage dirs** (`core/`, `logical/`, `sys/`,
   `audit/`, `auth/` at the volume root) — rollback path until the
   restore test passes.

## Snapshot CronJob — LIVE 2026-11-06, FULLY WIRED (incl. healthchecks.io)

Steps 1–4 are DONE and verified: airgap applied + negative-tested;
ceremony run; CronJob applied out-of-band; manual first run green with
the object independently confirmed in the bucket; the healthchecks.io
check is wired (`HC_PING_VAULT_SNAPSHOT` in the git-ignored
`k8s/config.env` → `checktick-config-local`) and the ping was delivered
by a manual verification run. First scheduled run: 03:45 UTC nightly.

All three artifacts are committed/prepared (session 13):

1. **Airgap policy** — DONE in `k8s/vault.yaml` (committed): ingress on
   8200 for pods labelled `checktick.io/vault-snapshot: "true"` (mirror of
   the `checktick.io/db-client` pattern in
   `postgres-networkpolicy.yaml`) + the scoped 8201 self-allow. Applied
   with the window's step 4. **Negative-test it after applying**: an
   UNlabelled pod must still time out reaching `vault:8200`.
2. **Mint** policy `vault-snapshot` + AppRole `vault-snapshot`:
   **`s/k8s-vault-snapshot-ceremony`** (generate-root → policy
   `sys/storage/raft/snapshot` ONLY — see Verification notes for the
   found-live endpoint → batch-token AppRole, 90-day secret_id → k8s Secret
   `vault-snapshot-approle` → root revoke). Re-run it at each quarterly
   restore rehearsal to rotate the secret_id (a missed rotation fails the
   nightly job; the healthchecks.io dead-man alert catches it same-night).
3. **CronJob** — **`k8s/vault-snapshot.yaml`**: 03:45 UTC (after the
   Longhorn 03:30 window; k8s cron is UTC), `concurrencyPolicy: Forbid`,
   pod label `checktick.io/vault-snapshot: "true"`, tmpfs working volume
   (the raw barrier snapshot never touches node disk). Flow:
   initContainer `snapshot` (vault CLI, AppRole login,
   `vault operator raft snapshot save`) → initContainer `encrypt`
   (`alpine:3.21` + `apk add age`, `age -r $AGE_RECIPIENT`, rm the raw tar)
   → container `upload` (aws cli + the Civo checksum env pair — see
   `postgres-cnpg.yaml`; creds `checktick-db-backup-creds`; uploads to
   `s3://checktick-backups/vault/`, prunes to the 14 newest, pings
   healthchecks.io on success only).
   **Deliberately NOT in kustomization.yaml** (the `postgres-cnpg.yaml`
   pattern — its prerequisites are out-of-band): apply with
   `kubectl apply -f k8s/vault-snapshot.yaml`. Prerequisites: the Secret
   from step 2, the ConfigMap from pre-flight (the AGE_RECIPIENT ref is
   non-optional ON PURPOSE — the job must FAIL rather than upload an
   unencrypted snapshot), and the healthchecks.io check: create it (daily
   03:45 UTC) and put `HC_PING_VAULT_SNAPSHOT=<ping-url>` in the
   git-ignored `k8s/config.env` → re-apply `checktick-config-local`.
4. **Verify the first run**:
   ```
   kubectl -n checktick create job --from=cronjob/vault-snapshot vault-snapshot-manual
   kubectl -n checktick logs -f job/vault-snapshot-manual
   ```
   Green logs + the `.age` object under `s3://checktick-backups/vault/`.
   Belt-and-braces: an `age --decrypt` dry-run on the operator laptop
   (Bitwarden private key) proves the recipient matches — do this before
   relying on the chain.

## Restore test (closes the runbook)

Restore the latest snapshot to a scratch Vault (drill pod, the
`s/k8s-restore-rehearsal` pattern): new PVC; download the newest
`vault-raft-*.tar.age` from `s3://checktick-backups/vault/`;
**`age --decrypt -i <operator key from Bitwarden>`** → `.tar`;
`vault operator raft snapshot inspect` it (sanity: version + key counts);
then **`vault operator raft snapshot restore <file>`** — VERIFIED SYNTAX,
and note the restore **returns before it completes**: wait for
`post-unseal setup complete` + `vault is unsealed` in the scratch pod's
log before testing further. Unseal with production shares (the restore
swaps the barrier), then read a KV escrow key. Record in
`docs/compliance/restoration-test-log.md`. **Only after this passes**:
delete the old file-storage dirs at the volume root (everything except
`raft/`), retire the interim tarball note, and mark hardening item 1 done
in `docs/civo-kubernetes-operations.md`.

## Rollback (any point before the restore test passes)

Revert the ConfigMap to `storage "file" { path = "/vault/storage" }`
(keep the new `/vault/storage` mount — the data did not move, only the
attach point), scale to 0 and back to 1, unseal. The migrate COPIES — it
does not move — so the file data is intact. The one artifact it leaves in
the source is the migration LOCK key; a stale lock makes Vault refuse to
start — clear it with `vault operator migrate -config=... -reset` (and
delete the `/vault/storage/raft` destination dir before re-trying
anything).

## Related

- `k8s/vault.yaml` — current manifest (ConfigMap + STS edited at the
  window; the airgap is already the post-migration form)
- `k8s/vault-snapshot.yaml` — the nightly ENCRYPTED snapshot CronJob
  (apply out-of-band, after the window + ceremony)
- `s/k8s-vault-snapshot-ceremony` — the AppRole mint for the snapshot job
- `k8s/scratch-vault-raft-migrate.yaml` — the one-shot migrate helper
  (git-ignored scratch)
- `s/k8s-vault-unseal`, `s/k8s-vault-ceremony` — ceremony tooling
- `docs/civo-kubernetes-operations.md` — Vault Operations section
- `k8s/POC-STATUS.md` session 13 — this prep session's log
