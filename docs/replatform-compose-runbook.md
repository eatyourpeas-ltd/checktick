---
title: Replatform Runbook — Civo Kubernetes to Docker Compose
category: self-hosting
priority: 9
---

# Replatform Runbook: Civo Kubernetes → Docker Compose (two-box)

**Status:** DRAFT — written 21/11/2026 during INC-03 (Civo platform-wide network
outage, 06:35–~17:30 UTC). Service was restored and recovery verified the same
day (healthz ok, Vault unsealed, 0 pod restarts). Execute the extraction phase
only while the Civo cluster remains reachable.

**Justification:** three availability incidents in the first three weeks on
Civo (INC-01, INC-02, INC-03 — see the Incident & Near-Miss Log), the last a
provider-side total outage of 11+ hours that no in-cluster architecture could
mitigate. At 2 nodes the k8s cluster also cannot survive node loss (2-member
etcd has no quorum majority), so compose offers the same worst case (total
loss → restore from backup) at a fraction of the operational load.
Zero-downtime deploys — the original reason for moving to k8s — are preserved
via blue/green (Phase 6).

**Topology: two boxes.**

- **Box A — production** (Mythic Beasts **VPS 16**, 16GB/4core, £48/mo):
  web blue/green, PostgreSQL 17, Vault, nginx, scheduled tasks.
- **Box B — staging + utility** (Mythic Beasts **VPS 8**, 8GB/2core, £25/mo):
  staging stack, **second copy of nightly backups**, disaster-recovery drill
  target, monitoring scripts.

Rationale for 2 not 3: compose has no quorum requirement, so a third box buys
nothing architecturally; a hot-standby third box re-introduces the replication
machinery this move removes. Data instead lives in **three** physical
locations (box A, box B, MB backup space mirrored to a second site), and
service recovery is covered by a **drilled** rebuild onto box B (Phase 9).
Revisit a third box only if a risk assessment sets an RTO a drilled rebuild
cannot meet.

**Budget:** £48 + £25 + 2 × IPv4 (£6.60 each per the order page) + disk
(40GB box A + 20GB box B; order page showed SSD at 8p/GB — verify at order
time) ≈ **£91–102/mo**. Yearly billing (12 for the price of 10) reduces ~17%.
Managed hosting (£99/mo) declined: it covers the OS layer only, and
unattended-upgrades + existing StatusCake/healthchecks.io monitoring cover the
same ground for ~£0. Revisit after 3 months if patching proves burdensome.

**SNOMED memory note:** the 8 GiB requirement belongs to the `sct ndjson`
step of `update_snomed_db` (docs/self-hosting-scheduled-tasks.md) — that build
runs in CI (`build-snomed-db.yml`, free 16GB runner) and must NEVER run on
these boxes. The on-box job is `import-snomed-db` (download prebuilt
`snomed.db` + `seed_snomed_datasets --force`), which the k8s manifest caps at
**1 Gi**. If a build is ever needed on-demand, use MB's per-second on-demand
billing for a temporary large VPS.

**Security invariants carried over unchanged:**

- `PLATFORM_CUSTODIAN_COMPONENT` must NEVER appear in any environment file
  (settings.py hard-fails; docs/vault.md control F6).
- Never `vault operator init` against migrated Vault storage — unseal with the
  EXISTING shares. A fresh init makes every encrypted survey permanently
  undecryptable.
- No secrets or real hostnames in this repository. The `.env` files live on
  the boxes only (and in the operator's password manager), never in git.

---

## 1. Target architecture

| Component | Box | Implementation | Notes |
| :--- | :--- | :--- | :--- |
| Web app | A | 2 × app container (`web-blue` / `web-green`) behind nginx | Blue/green for zero-downtime deploys |
| Database | A | `postgres:17` container (pin the minor) | **17, not the 16-alpine in `docker-compose.registry.yml`** — the dump comes from PostgreSQL 17 |
| Vault | A | `hashicorp/vault:1.21.4`, integrated Raft, manual unseal | Same version as the k8s deployment — never restore into an older Vault |
| Reverse proxy / TLS | A | nginx + certbot (Let's Encrypt) | Same domain, same DNS |
| Scheduled tasks | A | Host crontab → `docker compose exec` | Mirrors the 13 k8s CronJobs (Phase 5) |
| Nightly backups | A → B + MB | `pg_dump` + Vault raft snapshot + media tar → MB backup space (mirrored to a second site) **and** a copy to box B | Replaces CNPG/object-store backups; solves the INC-03 cross-provider backup gap |
| Staging | B | Full compose project (own DB, offset ports, own cert) | Replaces `k8s/staging-web.yaml` |
| DR drill target | B | Rehearsed rebuild of the prod stack (Phase 9) | The cheapest availability win at this budget |
| Media / SNOMED | A | Local disk bind mounts | All Longhorn/RWX/NFS complexity disappears |

---

## 2. Phase 0 — before extraction (do now)

### 2.1 OS choice

**Debian 13 (trixie), using Mythic Beasts' pre-built template image WITHOUT
Sympl, on BOTH boxes** (one hardening procedure, one patching story).
Rationale:

- Foundation-governed OS — no corporate owner — keeps the sovereignty chain
  clean end-to-end: Mythic Beasts (UK) → Debian (foundation) → our containers.
- MB are long-standing Debian operators; their template is minimal and their
  support staff know it intimately.
- No snap/telemetry baggage; `unattended-upgrades` gives the auditable
  security-patching story the compliance docs assume.
- Support runway: security fixes to ~mid-2028, Debian LTS to ~2030.
- **Without Sympl**: Sympl is MB's hosting platform for multi-site web + email
  hosting — it takes over the host's web-server config and ports 80/443 and
  pulls in an email stack (exim/dovecot) the box does not need. CheckTick is
  a single compose appliance with its own nginx container and certbot; adding
  Sympl would create config conflicts and unnecessary attack surface on a
  medical application's host.

Avoid: bullseye (EOL), jammy (aging LTS), noble (superseded by resolute).
Ubuntu 26.04 is an acceptable alternative if Debian is unavailable; Rocky is
not recommended (US-based governance, different patching tooling, no benefit
for this stack).

### 2.2 Initial hardening (both boxes, as root on the fresh template)

```bash
apt update && apt -y full-upgrade

# Deploy user; SSH keys only
adduser --disabled-password --gecos "" deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
# -> copy the operator public key(s) into /home/deploy/.ssh/authorized_keys (chmod 600)
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# Security-only unattended upgrades (the patching story for both boxes)
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
# verify /etc/apt/apt.conf.d/50unattended-upgrades enables ONLY the
# security origin (no -backports, no point releases)

# Firewall
apt install -y ufw
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80,443/tcp    # box B: 22/tcp + staging ports only
ufw enable

# Time sync — cron schedules and TLS depend on it
apt install -y chrony
```

Docker from Docker's official apt repo (current engine + compose v2 plugin;
NOT the distro `docker.io` package):

```bash
apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian trixie stable" \
  > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Record the build in `docs/compliance/standard-build-specification.md` and the
boxes in `asset-register.md` / `hardware-assets.md` as part of this step —
the build is only compliant if it is the documented one.

### 2.3 Remaining Phase 0 steps

1. Order both VPS (Debian 13 template **without Sympl**, IPv4 add-on on
   both); note their IPv4 addresses (`<PROD_IP>`, `<UTILITY_IP>`). If the
   order flow allows choosing the data centre, put box B in a **different
   site** from box A.
2. Run §2.2 on both boxes (box A additionally: nginx + certbot when the
   compose stack is built in Phase 2).
3. Directory layout, box A:

   ```text
   /srv/checktick/
     docker-compose.yml     # from Phase 2
     nginx/                 # conf.d + upstream fragment
     .env                   # assembled from k8s env files (Phase 2) — chmod 600
     .live-colour           # blue/green state (Phase 6)
     media/                 # restored from the media PVC
     snomed/                # snomed.db restored from the PVC
     vault/                 # vault storage + config
     backups/               # nightly local staging before off-box copy
   ```

   Box B: `/srv/staging/` (same shape) + `/srv/backups/checktick/` (backup
   copy target).

4. Lower the DNS TTL for the production hostname to 300s (≥24h before
   cutover).
5. Verify you hold: 3 of 4 Vault unseal keys, the operator age private key
   (Bitwarden), and the Civo object-store credentials (snapshot fallback).

---

## 3. Phase 1 — extraction from Civo

Work from a machine with the Civo kubeconfig
(`export KUBECONFIG=~/.kube/civo-checktick.yaml`; confirm with
`kubectl config current-context`).

### 3.1 Database (production)

```bash
kubectl get pods -n checktick -l cnpg.io/cluster=<cnpg-cluster-name> -o wide
kubectl exec -n checktick <cnpg-primary-pod> -- \
  pg_dump -U checktick -Fc -d checktick -f /tmp/checktick-prod.dump
kubectl cp -n checktick <cnpg-primary-pod>:/tmp/checktick-prod.dump ./checktick-prod.dump
sha256sum checktick-prod.dump | tee checktick-prod.dump.sha256
```

Record row counts for the post-restore sanity check (e.g. `surveys_survey`).
Staging DB: dump it too, or rebuild staging fresh on box B and skip.

### 3.2 Vault (the critical step)

The storage copy must happen while Vault is **sealed** (barrier-encrypted,
quiescent). Do NOT init anything.

```bash
kubectl exec -n checktick vault-0 -- vault operator seal
kubectl exec -n checktick vault-0 -- tar czf /tmp/vault-storage.tar.gz -C /vault storage config
kubectl cp -n checktick vault-0:/tmp/vault-storage.tar.gz ./vault-storage.tar.gz
sha256sum vault-storage.tar.gz | tee vault-storage.tar.gz.sha256
```

The tar contains `/vault/storage` (integrated Raft data, barrier-encrypted at
rest) and `/vault/config` (config.hcl — no secrets). Copy to box A over scp.
Keep a second copy for the box B drill.

### 3.3 Vault fallback artefact: fresh raft snapshot

If the storage-copy restore fails, the fallback is a snapshot restore. Take a
fresh snapshot while the source is healthy:

```bash
kubectl create job --from=cronjob/vault-snapshot vault-migration-snap -n checktick
kubectl wait --for=condition=complete job/vault-migration-snap -n checktick --timeout=10m
# Download the newest vault-raft-*.tar.age from the object store
# (checktick-db-backup-creds), then decrypt with the operator age key:
age --decrypt -o vault-raft-migration.snap vault-raft-<date>.tar.age
```

Keep the `.snap` encrypted at rest until used; delete after the migration.

### 3.4 Media and SNOMED

```bash
kubectl exec -n checktick deploy/checktick-web -- tar czf - -C /app media | tar xzf -
kubectl exec -n checktick deploy/checktick-web -- cat /snomed-source/snomed.db > snomed.db
sha256sum snomed.db | tee snomed.db.sha256
```

(SNOMED is also reconstructible from the object-store artifact — the copy is
a convenience, not a necessity.)

---

## 4. Phase 2 — environment and configuration

### 4.1 The `.env` model

Compose uses **one** `.env` file per project. Assemble box A's from the two
k8s files — same `KEY=VALUE` names (settings.py reads the same variables):

- **Values unquoted, no inline trailing comments** — same rule as the k8s
  env-files (`kubectl --from-env-file` stores values raw; compose dotenv
  strips surrounding quotes, so unquoted is safe in both worlds).
- **Delete lines you don't want set** — a blank `KEY=` overrides the
  settings.py default with an empty string.
- `chmod 600`. Never commit.

### 4.2 Mapping from the k8s files

| Source | Treatment |
| :--- | :--- |
| `k8s/config.env` (non-secret overlay) | Copy across **except**: `ALLOWED_HOSTS` / `ALLOWED_HOSTS_EXTRA` (drop the in-cluster entries — keep the public domains), `FORWARDED_ALLOW_IPS` (set to the compose network range, e.g. `172.16.0.0/12`), `STAGING_SITE_URL` (goes to box B's env), `LOGS_*` (drop — OpenObserve does not migrate initially) |
| `k8s/secrets.env` (credentials) | Copy across **except**: `DATABASE_URL` / `STAGING_DATABASE_URL` (the compose file constructs `DATABASE_URL` from a **NEW** `POSTGRES_PASSWORD` — never reuse a credential from the previous platform), `VAULT_ROLE_ID` / `VAULT_SECRET_ID` (carry over unchanged — they live in the migrated Vault storage) |
| New keys to add | `POSTGRES_PASSWORD=<new strong password>`, `VAULT_ADDR=http://vault:8200` (in-container plaintext on the private compose network), `WEB_IMAGE=ghcr.io/eatyourpeas-ltd/checktick:<released-tag>` (pin a released tag — never `latest`) |

### 4.3 Compose file (box A)

`/srv/checktick/docker-compose.yml` — blue/green web pair, PostgreSQL 17,
Vault, nginx:

```yaml
services:
  web-blue:
    image: ${WEB_IMAGE}
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql://checktick:${POSTGRES_PASSWORD}@db:5432/checktick
      VAULT_ADDR: http://vault:8200
      FORWARDED_ALLOW_IPS: 172.16.0.0/12
    volumes:
      - ./media:/app/media
      - ./snomed:/app/data
    depends_on: [db, vault]
    networks: [checktick]

  web-green:
    image: ${WEB_IMAGE}
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql://checktick:${POSTGRES_PASSWORD}@db:5432/checktick
      VAULT_ADDR: http://vault:8200
      FORWARDED_ALLOW_IPS: 172.16.0.0/12
    volumes:
      - ./media:/app/media
      - ./snomed:/app/data
    depends_on: [db, vault]
    networks: [checktick]

  db:
    image: postgres:17-alpine   # pin the exact minor at build time
    restart: unless-stopped
    environment:
      POSTGRES_DB: checktick
      POSTGRES_USER: checktick
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U checktick"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks: [checktick]

  vault:
    image: hashicorp/vault:1.21.4
    restart: unless-stopped
    cap_add: [IPC_LOCK]
    volumes:
      - ./vault/storage:/vault/storage
      - ./vault/config:/vault/config   # config.hcl from the migrated tar
    networks: [checktick]

  nginx:
    image: nginx:stable-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/upstream.conf:/etc/nginx/conf.d/upstream.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [web-blue, web-green]
    networks: [checktick]

networks:
  checktick:
    driver: bridge
```

`vault/config/config.hcl` (comes out of the migrated tar; verify it reads):

```hcl
storage "raft" {
  path    = "/vault/storage/raft"
  node_id = "vault-1"
}
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true   # plaintext on the private compose network only
}
api_addr     = "http://vault:8200"
cluster_addr = "http://vault:8201"
ui           = false
```

`nginx/upstream.conf` (the deploy script rewrites the active line):

```nginx
upstream checktick_app { server web-blue:8000; }   # deploy script manages this file
```

`nginx/conf.d/checktick.conf`: standard 80→443 redirect + TLS server block
proxying to `checktick_app` (`proxy_set_header Host $host;`,
`X-Forwarded-Proto https`, `client_max_body_size` to taste). Obtain the
certificate with certbot webroot before first start, or start nginx HTTP-only
first and certbot afterwards.

---

## 5. Phase 3 — restore (box A)

### 5.1 Vault (do this FIRST — the app cannot decrypt anything without it)

```bash
cd /srv/checktick
tar xzf vault-storage.tar.gz            # unpacks ./vault/storage + ./vault/config
docker compose up -d vault
docker compose exec -T vault sh -c 'VAULT_ADDR=http://127.0.0.1:8200 vault status'
# Expect: Sealed true, Total Shares 4, Threshold 3 — the ORIGINAL seal config.
# NEVER run vault operator init.

# Unseal with the EXISTING shares (3 of 4):
docker compose exec -T vault sh -c 'VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal <key1>'
# ... repeat for key2, key3
```

**Fallback (only if the storage copy fails to start):** initialise a throwaway
single-node Vault, unseal it, then `vault operator raft snapshot restore
-force vault-raft-migration.snap`, restart, and unseal with the ORIGINAL
shares (the snapshot carries the original seal configuration). Verify against
current HashiCorp docs before relying on this path.

**AppRole check:** the migrated storage carries the AppRole, so the existing
`VAULT_ROLE_ID` / `VAULT_SECRET_ID` should authenticate. Verify after the web
stack is up (`/healthz` reports `vault: ok`). If the `secret_id` has expired:
recover a root token via `vault operator generate-root` (needs the unseal
shares), mint a fresh `secret_id` for the existing AppRole, update `.env`, and
revoke the root token again.

### 5.2 Database

```bash
cd /srv/checktick
docker compose up -d db                     # wait for healthy
cat checktick-prod.dump | docker compose exec -T db pg_restore -U checktick \
  -d checktick --no-owner --role=checktick --exit-on-error
docker compose exec -T db psql -U checktick -d checktick -c \
  'select count(*) from surveys_survey;'    # sanity vs the pre-migration count
```

No migrations are needed — the schema is restored at the same version.

### 5.3 Media and SNOMED

```bash
rsync -a media/ /srv/checktick/media/
install -m 644 snomed.db /srv/checktick/snomed/snomed.db
```

---

## 6. Phase 4 — verification (box A)

1. `docker compose up -d` (web-blue live; `.live-colour` = `blue`).
2. From the box: `curl -sf localhost/healthz` (through nginx) → `status: ok`
   — DB reachable, Vault unsealed, SNOMED present.
3. Run the existing smoke gate against the new host:
   `python3 k8s/smoke-test.py --host https://<domain>` (19 checks including the
   encrypt/decrypt round-trip).
4. Manual round-trip: log in, create a survey, submit a response, view it —
   this proves DB + Vault + key hierarchy together on the new stack.
5. Check the Django admin, a payment webhook sandbox event if practical, and
   one outbound email.

---

## 7. Phase 5 — scheduled tasks and backups (box A)

`sudo crontab -e` on box A — mirrors the 13 k8s CronJobs
(`k8s/cronjobs.yaml`); each pings healthchecks.io on success exactly as the
k8s jobs did:

```cron
CRON_TZ=UTC
0  2 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_data_governance && if [ -n "$HC_PING_PROCESS_DATA_GOVERNANCE" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_DATA_GOVERNANCE" > /dev/null; fi'
10 2 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py cleanup_survey_progress && if [ -n "$HC_PING_CLEANUP_SURVEY_PROGRESS" ]; then curl -fsS --retry 3 "$HC_PING_CLEANUP_SURVEY_PROGRESS" > /dev/null; fi'
20 2 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py sync_external_datasets && if [ -n "$HC_PING_SYNC_EXTERNAL_DATASETS" ]; then curl -fsS --retry 3 "$HC_PING_SYNC_EXTERNAL_DATASETS" > /dev/null; fi'
30 2 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py sync_global_question_group_templates && if [ -n "$HC_PING_SYNC_GLOBAL_QUESTION_GROUP_TEMPLATES" ]; then curl -fsS --retry 3 "$HC_PING_SYNC_GLOBAL_QUESTION_GROUP_TEMPLATES" > /dev/null; fi'
40 2 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py prune_unconfirmed_users && if [ -n "$HC_PING_PRUNE_UNCONFIRMED_USERS" ]; then curl -fsS --retry 3 "$HC_PING_PRUNE_UNCONFIRMED_USERS" > /dev/null; fi'
0  3 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_expired_subscriptions && if [ -n "$HC_PING_PROCESS_EXPIRED_SUBSCRIPTIONS" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_EXPIRED_SUBSCRIPTIONS" > /dev/null; fi'
5  3 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_expiring_subscriptions && if [ -n "$HC_PING_PROCESS_EXPIRING_SUBSCRIPTIONS" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_EXPIRING_SUBSCRIPTIONS" > /dev/null; fi'
10 3 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_promotion_lifecycle && if [ -n "$HC_PING_PROCESS_PROMOTION_LIFECYCLE" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_PROMOTION_LIFECYCLE" > /dev/null; fi'
15 3 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_dsr_deadlines && if [ -n "$HC_PING_PROCESS_DSR_DEADLINES" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_DSR_DEADLINES" > /dev/null; fi'
20 3 * * *  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_diary_reminders && if [ -n "$HC_PING_PROCESS_DIARY_REMINDERS" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_DIARY_REMINDERS" > /dev/null; fi'
0  4 * * 0  cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py sync_nhs_dd_datasets && if [ -n "$HC_PING_SYNC_NHS_DD_DATASETS" ]; then curl -fsS --retry 3 "$HC_PING_SYNC_NHS_DD_DATASETS" > /dev/null; fi'
*/15 * * * * cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py process_recovery_time_delays && if [ -n "$HC_PING_PROCESS_RECOVERY_TIME_DELAYS" ]; then curl -fsS --retry 3 "$HC_PING_PROCESS_RECOVERY_TIME_DELAYS" > /dev/null; fi'
0  14 * * 2 cd /srv/checktick && docker compose exec -T web-blue sh -c 'python manage.py seed_snomed_datasets --force && if [ -n "$HC_PING_IMPORT_SNOMED_DB" ]; then curl -fsS --retry 3 "$HC_PING_IMPORT_SNOMED_DB" > /dev/null; fi'
```

Note: crontab targets `web-blue` explicitly — after a deploy the live colour
flips, so either target the nginx-routed service via
`docker compose exec -T nginx`-style indirection, or have `deploy.sh` rewrite
a `cron-target` file the crontab reads. Simplest robust option: run the
management commands through a short wrapper script
(`/srv/checktick/s/cron.sh <command...>`) that reads `.live-colour` and execs
into the live container — the crontab then never changes.

(The `update_snomed_db` TRUD build runs from CI as today; the Tuesday 14:00
slot imports the built db. TRUD is offline 18:00–08:00 UK — keep slots in UK
business hours.)

Nightly backups (add before decommissioning Civo — this becomes the system of
record):

```cron
30 3 * * * /srv/checktick/s/backup-nightly.sh
```

`backup-nightly.sh`: `pg_dump -Fc` + `vault operator raft snapshot save`
(age-encrypted with the operator recipient, as today) + media tar → upload to
MB backup space (mirrored to MB's second site) **and** `rsync` to
`box-B:/srv/backups/checktick/` → ping healthchecks.io on success only.

---

## 8. Phase 6 — zero-downtime deploys (blue/green, box A)

`/srv/checktick/s/deploy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
TAG="$1"; [ -n "$TAG" ] || { echo "usage: deploy.sh <released-tag>"; exit 1; }
cd /srv/checktick
LIVE=$(cat .live-colour)                       # blue | green
NEXT=$([ "$LIVE" = blue ] && echo green || echo blue)
export WEB_IMAGE="ghcr.io/eatyourpeas-ltd/checktick:${TAG}"

# 1. Migrations run BEFORE the switch (expand/contract discipline — old and
#    new app versions must both tolerate the schema during the transition)
docker compose run --rm web-"$NEXT" python manage.py migrate

# 2. Start the new colour and health-check it directly
docker compose up -d --no-deps "web-$NEXT"
for i in $(seq 1 30); do
  docker compose exec -T nginx curl -fsS "http://web-$NEXT:8000/api/health" >/dev/null && break
  [ "$i" = 30 ] && { echo "health check failed; $LIVE still serving"; exit 1; }
  sleep 2
done

# 3. Flip the upstream (new primary, old as backup for in-flight drain) and reload
cat > nginx/upstream.conf <<EOF
upstream checktick_app {
    server web-$NEXT:8000;
    server web-$LIVE:8000 backup;
}
EOF
docker compose exec -T nginx nginx -s reload

# 4. After the drain window, retire the old colour
sleep 15
docker compose stop "web-$LIVE" && docker compose rm -f "web-$LIVE"
echo "$NEXT" > .live-colour
echo "deployed $TAG on $NEXT"
```

Rollback = run the script again with the previous tag. CI: adapt
`.github/workflows/deploy-civo.yml` into a `deploy-compose.yml` (SSH action →
`deploy.sh <tag>` + smoke check) once manual deploys are proven; until then
deploy manually per release.

---

## 9. Phase 7 — staging and the DR drill (box B)

### 9.1 Staging

Full compose project at `/srv/staging` (own `.env` with its own local DB,
`ENVIRONMENT=staging`, offset host ports, e.g. nginx on 8080/8443 behind a
`staging.<domain>` vhost + its own cert). Restore the staging dump from
Phase 1 or rebuild fresh. The single staging cron
(`prune-unconfirmed-users`) goes in box B's crontab.

### 9.2 DR drill (run BEFORE the cutover, then quarterly)

The drill is the availability story for this architecture — a rehearsed
rebuild beats an unpracticed hot standby:

1. On box B, build the prod stack from the runbook alone (compose file, `.env`
   copy, restored `pg_dump`, Vault storage copy + unseal, media/snomed) —
   using only the documentation and the artefacts, no improvisation.
2. Time it. That number is the **RTO**; the WAL archiving frequency is the
   **RPO**. Record both in `annual-disaster-recovery-drill.md` and
   `restoration-test-log.md`.
3. Verify `/healthz` + the encrypt/decrypt round-trip on the drill stack.
4. Tear the drill stack down (it must never run simultaneously with prod
   against the same Vault AppRole identity — it is a copy, isolated on box B).

If the drill exposes gaps (missing steps, undocumented values), fix the
runbook immediately — that is its purpose.

---

## 10. Phase 8 — cutover

1. Announce a short maintenance window (the site has effectively been down
   anyway — INC-03).
2. On Civo: final `pg_dump` (repeat 3.1) for any data written since the first
   dump; repeat the Vault seal+copy **only if** the app wrote encrypted data
   since (if Vault was sealed the whole time, the Phase 1 copy is still
   current — check `vault status` seal state and the DB row counts).
3. Restore the delta on box A (repeat 5.2).
4. Switch DNS A record → `<PROD_IP>` (TTL 300). certbot already holds the
   cert.
5. Watch `/healthz`, StatusCake, healthchecks.io pings, and error emails for
   24h.
6. **Keep the Civo cluster intact for a rollback window (suggest 2 weeks).**
   Rollback = switch DNS back (data written on box A in the meantime would
   need a reverse dump — keep the window short or accept the loss).

---

## 11. Decommissioning Civo (after the rollback window)

1. Final `pg_dump` + Vault raft snapshot + media tar from box A → MB backup
   space + box B (the new system of record).
2. Cancel Civo resources (cluster, CNPG, object store — **after** confirming
   the new backups are restorable).
3. Update the compliance set (next section) and close INC-03.

---

## 12. Compliance updates required by this move

- `service-map.md`, `cloud-responsibility-matrix.md`, `supplier-register.md`,
  `supplier-assurance-mapping.md` — Civo out, Mythic Beasts in (UK-owned,
  founder/staff-owned, no external investors; complete supplier assurance).
- `asset-register.md`, `hardware-assets.md`, `ip-address-register.md`,
  `information-asset-register.md` — two boxes, new IPs, new storage locations.
- `backup-policy.md`, `backup-isolation-procedure.md`, `restoration-test-log.md`
  — new backup path (MB backup space mirrored to a second site + box B copy);
  schedule the first restoration test (the Phase 9 drill doubles as this).
- `business-continuity-plan.md`, `incident-response-plan.md`,
  `annual-disaster-recovery-drill.md` — two-box failure modes, RTO/RPO figures
  from the drill, unseal-after-reboot procedure.
- `patch-management-strategy.md`, `continuous-patching-lifecycle.md`,
  `standard-build-specification.md` — self-managed Postgres/OS patching (or MB
  managed hosting if later adopted), Dependabot-driven image bumps, and the
  documented Debian 13 box build (§2.2) as the standard build.
- `risk-register.md` — new box-A availability risk entry; INC-03 closure
  evidence.
- `network-security-policy.md`, `encryption-transit.md` — Vault plaintext on
  the private compose network; TLS termination at nginx.

---

## 13. Open risks to accept or address

- **Box A is a single point of failure for service.** Hardware/host loss =
  outage until the drilled rebuild completes on box B (RTO target: ≤2h,
  measured by the Phase 9 drill). Mitigations: MB dual power/network feeds,
  nightly mirrored backups (three locations), drilled rebuild, fallback page.
- **Vault re-seals on every host reboot** — unseal ceremony needed after any
  box A reboot (planned-availability window; document on the box).
- **No DB replication** — RPO bounded by WAL archiving frequency (tune to
  ≤15 min).
- **DNS / single IP per box** — keep a secondary DNS provider if not already;
  the degraded-mode fallback page (served from outside the boxes) remains a
  hardening item from INC-03.
