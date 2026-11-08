---
title: "Infrastructure Technical Change Log"
category: dspt-9-it-protection
---

# Infrastructure Technical Change Log

**Organisation:** EatYourPeas Ltd
**Document Owner:** Dr Simon Chapman (CTO) & Dr Serena Haywood (SIRO)
**Last Reviewed:** April 2026
**Scope:** Boundary firewalls, cloud infrastructure (PaaS/SaaS),
DNS management, and end-user device configurations.

---

## 1. Annual Infrastructure & Firewall Review Schedule

In accordance with Cyber Essentials Plus requirements, a formal
review of all network security settings is performed at least
once every 12 months.

| Scheduled Date | Review Category | Assigned Auditor | Completion Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| Feb 2026 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | 07/02/2026 | ✅ Completed |
| Feb 2027 | Firewall, Cloud & DNS Audit | Dr Simon Chapman (CTO) | — | Pending |

### Review Checklist

**Network Equipment**

- [ ] Verify router admin password is 12+ characters, unique,
  and stored in Bitwarden
- [ ] Confirm remote management is disabled on the router
- [ ] Confirm UPnP is disabled on the router
- [ ] Verify no inbound port forwarding rules exist
  (deny by default)
- [ ] Confirm router firmware is on current supported version

**Device Security**

- [ ] Confirm all device local firewalls are enabled
- [ ] Verify only necessary user accounts exist on all devices
- [ ] Confirm guest accounts disabled on all Mac devices
- [ ] Verify one standard user account per device
- [ ] Confirm administrator accounts used only with password
  manager authentication
- [ ] Remove any test, temporary, or unused accounts
- [ ] Verify all default passwords changed on all devices
- [ ] Confirm mobile devices have 6+ digit PIN or biometric
  lock enabled
- [ ] Verify Quad9 (9.9.9.9) configured as DNS resolver on
  all devices

**Cloud and SaaS Access**

- [ ] Audit user access to GitHub — remove any unnecessary
  accounts
- [ ] Audit user access to Northflank — remove any unnecessary
  accounts
- [ ] Audit user access to Microsoft 365 — confirm only named
  administrators have global admin rights
- [ ] Verify MFA active on all GitHub accounts
- [ ] Verify MFA active on all Northflank accounts
- [ ] Verify MFA enforced at Microsoft 365 tenant level
- [ ] Verify MFA active on Namecheap DNS management account
- [ ] Confirm no default or guessable passwords on any cloud
  accounts
- [ ] Verify Microsoft Graph API application registration
  scoped to Mail.Send only — confirm no additional permissions
  have been granted
- [ ] Review Northflank service tokens — confirm scope and
  expiry
- [ ] Verify Microsoft Graph API client secret expiry date
  and rotate if within 30 days

**DNS Management**

- [ ] Verify Namecheap console access restricted to named
  administrators only
- [ ] Confirm no unauthorised DNS record changes since last
  review
- [ ] Review all current DNS records for checktick.uk and
  confirm accuracy
- [ ] Verify checktick.uk SPF record authorises Microsoft 365
  sending infrastructure correctly
- [ ] Verify checktick.uk DKIM CNAME records are present and
  valid
- [ ] Verify checktick.uk DMARC record is active (p=quarantine
  minimum)
- [ ] Confirm 2FA active on Namecheap account

---

## 2. Change Log

### 2a. Firewall & Inbound Rule Changes

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 07/02/2026 | Dr Simon Chapman | Policy baseline established — deny by default inbound configuration documented | Initial CE+ compliance baseline | Dr Serena Haywood (SIRO) | ✅ Active |
| 07/02/2026 | Dr Simon Chapman | Router admin credential updated to 12+ character unique password stored in Bitwarden | CE+ requirement — no default credentials | Dr Serena Haywood (SIRO) | ✅ Active |

### 2b. DNS Record Changes (checktick.uk)

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Apr 2026 | Dr Simon Chapman | MX records updated to point to Microsoft 365 Exchange Online | Migration to Microsoft 365 for DCB1596 compliance | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | SPF record updated to authorise Microsoft 365 sending infrastructure | DCB1596 compliance — Microsoft 365 migration | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | DKIM CNAME records added for Microsoft 365 signing | DCB1596 compliance — Microsoft 365 migration | Dr Serena Haywood (SIRO) | ✅ Active |
| Apr 2026 | Dr Simon Chapman | DMARC record set to p=quarantine pct=100 | DCB1596 compliance — enforce authentication on all outbound email | Dr Serena Haywood (SIRO) | ✅ Active |
| 03/11/2026 | Dr Simon Chapman | Production A record for `checktick.uk` repointed from the Northflank CNAME chain (`lb.649c046f7793c53a50fe4bcf.northflank.com`) to 74.220.17.170 (Civo Kubernetes ingress, London LON1); record TTL lowered to 60s in advance of the change | Final step of the Northflank → Civo production migration window (runbook `docs/migration-northflank-to-civo.md` Phase 4 step 10) — UK-region hosting following the Northflank security incident | Dr Serena Haywood (SIRO) | ✅ Active |

### 2c. Cloud Infrastructure Changes

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Apr 2026 | Dr Simon Chapman | Microsoft 365 Business Basic tenant provisioned for checktick.uk domain | DCB1596 secure email compliance for health and care communications | Dr Serena Haywood (SIRO) | ✅ Active |
| 03/11/2026 | Dr Simon Chapman | **Production cutover Northflank → Civo Kubernetes (LON1)** — see the incident driver and timings table below | Provider change driven by the Northflank security incident of 30/10/2026 (see below) and a preference for UK-sovereign infrastructure for this medical application; executed per the rehearsed runbook (both drills passed against real production data 2026-11-02) | Dr Serena Haywood (SIRO) | ✅ Active |
| 03/11/2026 | Dr Simon Chapman | NetworkPolicy `checktick-db-ingress` applied: PostgreSQL pods (CloudNativePG) accept connections on 5432 only from the Django web pods, the cluster's own instance pods (streaming replication / backups), and the CNPG operator — all other in-cluster sources denied (verified by negative test: non-allowed pod connection times out). Egress deliberately unrestricted — instance pods upload WAL/base backups to the Civo object store; a fragile allowlist would risk silently breaking point-in-time recovery. Vault airgap (`vault-airgap`: ingress web-only on 8200, egress fully denied) unchanged since the POC | Close the in-cluster network-segmentation gap identified in the cutover review: DB services are ClusterIP-only (never internet-exposed) but were reachable from any pod in the cluster; medical-data posture requires the DB to be reachable only by the application, consistent with the Vault airgap | Dr Serena Haywood (SIRO) | ✅ Active |
| 04/11/2026 | Dr Simon Chapman | NetworkPolicy `checktick-db-ingress` **revised**: `checktick.io/db-client=true` label added to all 13 CronJob pod templates + the pre-deploy Job template, and allowed explicitly in the policy — the 03/11 revision allowed only web/instance/operator pods and would have silently blocked every scheduled job from the database at the next 02:00 UTC batch. Found 04/11 by a manual test job (connection timeout reaching `checktick-db-rw`), fixed and re-verified same day (test job from the `process-data-governance` template ran to completion against the DB). Batch pods carried no labels, so the label IS their DB access grant — recorded in the policy comments | Correctness of the 03/11 airgap change: the medical-data posture requires the DB reachable by the application AND its scheduled maintenance jobs, and nothing else; the initial policy's omission of the batch class was an implementation defect, not a design intent | Dr Serena Haywood (SIRO) | ✅ Active |
| 04/11/2026 | Dr Simon Chapman | healthchecks.io ping wiring migrated: the 11 per-job ping URLs were extracted from the Northflank job definitions (pre-decommission) into the git-ignored runtime config (`HC_PING_*` — capability URLs never enter the public repo), and the Kubernetes CronJob commands now ping on success only (curl `&&` chain — a failed or non-running job sends no ping and healthchecks.io alerts by email). Verified end to end with a manual job run | Continuity of the DSPT-aligned scheduled-task failure alerting across the provider migration — including silent-failure modes like the 04/11 blocked nightly-backup schedule, which this alerting exists to catch | Dr Serena Haywood (SIRO) | ✅ Active |
| 04/11/2026 | Dr Simon Chapman | NetworkPolicy `checktick-db-ingress` **revised (port 8000)**: the CNPG instance-manager status API (port 8000) allowed explicitly for the CNPG operator (cnpg-system) and for the cluster's own instance pods — the 03–04/11 revisions allowed the operator on 5432 only, leaving it unable to poll instance status (`Instance Status Extraction Error / HTTP communication issue` every ~4s) and — critically — unable to deliver switchover/demote commands during node drains. Found during pre-flight for the same evening's CVE node-image upgrade (see next row); patched live and in `k8s/postgres-networkpolicy.yaml`, verified: operator log clean and `Cluster in healthy state` immediately after, then exercised for real by two CNPG primary switchovers during node recycles with zero write loss | Correctness of the DB airgap: the operator must reach the instance-manager API to coordinate primary switchover during node drains — without it a drain of the primary's node would stall against the PDB instead of switching over cleanly; medical-data posture requires the DB reachable by the application, its scheduled jobs, AND its lifecycle operator, and nothing else | Dr Serena Haywood (SIRO) | ✅ Active |
| 04/11/2026 | Dr Simon Chapman | **CVE-2026-98432 node-image patch + Kubernetes 1.35.0→1.36.0 upgrade** (evening window ~18:52–19:50 UTC): `civo k8s upgrade` to `1.36.0-k3s1` (found to be an IN-PLACE k3s binary bump — no kernel change), followed by `civo k8s recycle` of all 3 nodes one at a time (drain → delete → rebuild → rejoin), which delivered the patched node image: all nodes now **Alpine v3.23 / kernel 6.18.60-0-lts** (was Alpine v3.22 / 6.12.85-0-lts, vulnerable). Fresh base backups taken before the upgrade and before each recycle (4 total, all `completed`); WAL archiving continuous throughout. Vault survived storage re-attach and was unsealed by the operator (3-of-4 production shares) after the final recycle. External IP `74.220.17.170` unchanged throughout (cluster-managed floating IP — moves to a surviving node automatically; no DNS/kubeconfig/GitHub-secret changes needed). Post-verification: all nodes ≥ kernel 6.12.113 fix threshold, CNPG `Cluster in healthy state`, Longhorn volumes back to `healthy` (3 replicas after the 600s replenishment interval), both certs READY, `/healthz` fully ok, smoke test 19/19. Transient user impact: ~40s healthz blips at each CNPG switchover + 404 gaps during recycles + ~6 min sealed-Vault outage for the final recycle's unseal ceremony | **CVE-2026-98432** (use-after-free in kernel IPv4 TCP handshake, CVSS 9.8, fix in 6.12.113): all 3 nodes were internet-exposed TCP endpoints (Traefik DaemonSet on 80/443 + k3s API on 6443, Go ≥1.24 listeners with MPTCP — the exact configuration the demonstrated remote-root exploit targeted) running a pre-fix kernel; patching was time-critical for this medical platform. Runbook `docs/upgrade-civo-node-image-cve-2026-98432.md` (now retired) had pre-verified: no patched node image available at 1.35.0 (Civo support), 1.36.0-k3s1 required, CNPG operator compatible with k8s 1.36 | Dr Serena Haywood (SIRO) | ✅ Active |

| 06/11/2026 | Dr Simon Chapman | **Vault storage migration file → integrated Raft + nightly encrypted snapshot backups** — sealed window 17:48–18:03 UTC, existing 3-of-4 Shamir shares retained, post-migration smoke test 19/19; nightly 03:45 UTC CronJob takes a raft snapshot via a least-privilege AppRole (sys/storage/raft/snapshot only), encrypts it with an operator-held age key (private key in Bitwarden, never in repo/cluster), uploads to Civo Object Store (14-object retention) — the stored object requires BOTH the Shamir shares AND the operator's age private key; airgap NetworkPolicy extended (snapshot-pod ingress grant + scoped 8201 self-allow), negative-tested (unlabelled pod times out) | The Vault was the last component with no scheduled backup; file storage has no online snapshot path and a stop-copy cron would put unseal shares on a scheduled job (breaks the custody model). Nightly freshness is required because every survey creation writes escrow key material — a stale backup makes post-copy surveys permanently undecryptable | Dr Simon Chapman (CTO) | ✅ Active |
| 07/11/2026 | Dr Simon Chapman | **Node pool resize: 3× `g4s.kube.medium` → 1× `g4s.kube.large` (new second pool, `large`) + 2× medium (~$86/mo)** — approved ladder step 1. Pre-flight: backup chain green + fresh base backup `pre-pool-resize-20261107` (completed 17:47:48Z). Retire target `…-b966-8ciwh` (floating-IP holder + CNPG replica; the only node hosting neither `vault-0` nor the primary) cordoned + drained 17:48, instance deleted 17:49; floating IP `74.220.17.170` re-announced on the large node automatically; CNPG 2/2 healthy through the drain (primary untouched — a switchover came LATER, see below). **User-visible 404 window ~4–5 min (17:49–17:54), vs ~2 min predicted** — the drain evicts the Longhorn RWX share-manager for `checktick-media`; both web pods died on the NFS blip and replacements stalled `Init:0/2` on `FailedMount DeadlineExceeded` until the share-manager rebuilt on the large node. All 3 volumes back to healthy robustness by ~18:05; backup chain re-verified green post-change. **Log-collector DaemonSet NOT applied: post-resize both mediums sit at 88% working set** (requests-based packing + web anti-affinity put one web pod on each medium while the large node idles ~52–55%) — **go/no-go FAILED at 88/88, fixed same day by the redistribution** (~18:25–18:40 UTC): all 14 CronJobs + OpenObserve hard-pinned to the `large` pool and web given a soft preference for it (git-ignored `k8s/scratch-*` affinity patches, the `scratch-allowhosts` pattern — wiped by any manifest re-apply). The web rollout's boot spike on the primary's medium tripped db-1's status probe → **CNPG operator coordinated a CLEAN switchover (exit 0, ~40 s, data-safe; WAL chain unbroken, backup chain re-verified green) — primary `checktick-db-2` now on the large node**. Final steady state **45%/68%/76%** (was 99%/80%/72% before the day); collector DaemonSet still OFF pending the trimmed-footprint go/no-go (~79–80% on the mediums — edge of the 11-05 storm band). Runbook + traps: docs/civo-kubernetes-operations.md → Node Pool Resize. civo CLI v1.5.5 trap: `--name large` (under 6 chars) panics AFTER the API call succeeds — the pool IS created; verify with `node-pool ls` before retrying (a duplicate pool created this way was deleted same day, ~4 min of double billing) | Create the per-node memory headroom the OpenObserve log collector DaemonSet requires (hardening-backlog item 4): the approved halfway step between 3× medium (~$65/mo) and 3× large; tolerated-risk posture (availability, never data) unchanged | Dr Simon Chapman (CTO) | ✅ Active |
| 07/11/2026 | Dr Simon Chapman | CronJob `process-recovery-time-delays` cadence relaxed `*/5` → `*/15` (live cluster + `k8s/cronjobs.yaml` + `docs/self-hosting-scheduled-tasks.md` + `docs/compliance/patch-management-strategy.md`); the healthchecks.io dashboard check must be updated to `*/15` by the operator or it will alert false-late | The command is the SOLE flip of the ethical-recovery 24–48 h time delay (IN_TIME_DELAY → READY_FOR_EXECUTION + admin email + audit entry — no lazy flip in views), so it must RUN reliably, but the cadence only bounds admin-email latency (≤15 min on a 24–48 h control) and stuck-job detection; 288 → 96 Django boots/day, all pinned to the large node | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **OpenObserve log-collector DaemonSet go-live (trimmed profile) + the f985n engine-drift fix**: collector applied 08:41 UTC (all nodes ≥ ~400 Mi free at the go/no-go gate) and shipped 526,717 records / ~324 MB in ~20 min — but `f985n`, which had quietly gained ~250 Mi overnight (BOTH RWX volume engines + share-managers drifted onto it) and had liveness-killed its web pod at 08:38 pre-collector, killed it again at 89% → the documented rollback fired. Root-cause fix 09:00 UTC: both engines moved back to the large node (cordon both mediums → delete the two share-manager pods → rescheduled to the large node → uncordon; ~3 min user-visible NFS/404 window, web pods replaced cleanly, volumes back to healthy robustness, backup chain re-verified). Collector re-applied 09:06 UTC — LIVE and shipping; steady state large 53% / f985n 82% / hwp2f 78%. The hostPath tail DBs mean the backlog drain RESUMED from 11-05 21:35 (no duplicate re-ship of the 526,717 records already ingested); live logs appear once the remaining ~2.5-day backlog drains | Completes hardening-backlog item 4 (infrastructure log retention): the node-pool resize's purpose — per-node headroom for the collector — realised after fixing the overnight engine drift that had re-consumed it | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Nightly Vault snapshot failure (03:45 UTC) — found + fixed same morning**: the 0.27.0 deploy's roll-every-CronJob CI step set the OUT-OF-BAND `vault-snapshot` job's `upload` container to the app image (no aws CLI) → `aws: not found`, both backoff attempts failed, no upload and no HC ping (the missed ping IS the healthchecks.io alert path). Last good snapshot 07/11 03:45 → ~28 h escrow-freshness gap, closed by manual re-run `vault-snapshot-manual-20261108` (completed 08:06 UTC, `vault-raft-2026-11-08T080625.tar.age` uploaded; 14-object retention prune intact). Fixes: live image restored to `amazon/aws-cli:latest`; `deploy-civo.yml` now SKIPS `vault-snapshot` in the CronJob roll (out-of-band, purpose-built images: hashicorp/vault, alpine, amazon/aws-cli) — the roll only touches `containers`, which is why the init containers survived and the job reached the upload step | Nightly freshness of the Vault escrow-key backup is the control that keeps post-snapshot survey creation decryptable after a total Vault loss; CI must never re-image out-of-band CronJobs | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Node redesign 1× large + 2× medium → 2× `g4s.kube.large` (~$87/mo), cilium lease patch, and the wrong-pool deletion incident**: pre-flight base backup `pre-2large-redesign-20261108`; pool `large2` created (the CLI rejects scaling the 5-char `large` pool ID); `hwp2f` drained + retired (zero impact); `f985n` drained + retired with the rehearsed Vault re-seal ceremony (sealed ~09:57–10:07 UTC, unsealed by the operator); medium pool deleted. **INCIDENT: the `civo node-pool delete` for the medium pool ALSO deleted the `large` pool** (third CLI ID-handling bug — the response printed an empty pool name); Civo tore down `mbuc5` (repeated re-cordons + pod deletions); recovery: pool `large3` created, replacement node joined in ~5 min, all HA pairs rescheduled, floating IP auto-moved to `pve7x`, **no data loss — the DB + Vault PVCs are on `civo-volume` (provider-managed block storage), not Longhorn** — and the site never dropped below single-web-pod availability. Also applied: **cilium-operator leader-election lease patched 15s→90s** (interim for the lease-thrash root cause; operators stable since vs a crash every 5–15 min); Longhorn volumes set to 2 replicas (2-node reality; all healthy). End state: pools `large2`+`large3`, nodes ~48–60%, CNPG 2/2, collector live | The mediums' ~1.1 GiB/node platform tax (47% of a 2.33 GiB node) drove the entire week's placement crises; 2× large makes the storms structurally impossible at current load for the same monthly cost, and matches the intended staging+prod shared-volume architecture | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Staging environment stood up in the prod `checktick` namespace** (the 2× large redesign's matching step): web `deploy/checktick-staging-web` (1 replica, no PDB — a single-replica PDB would veto every drain; no topology spread) + Service on the SHARED media/SNOMED RWX PVCs (SNOMED free, no re-import); CloudNativePG `checktick-staging-db` (1 instance, `civo-volume` 10Gi, **no ScheduledBackup, no WAL archiving** — staging data is disposable) + its own `checktick-staging-db-ingress` NetworkPolicy; `vault-airgap` extended to admit `app=checktick-staging-web` (Vault + AppRole shared, `vault-0` untouched — no re-seal); exactly ONE staging CronJob `prune-unconfirmed-users-staging` with `EMAIL_BOUNCE_PROCESSING_ENABLED=false` (the shared prod mailbox stays out of staging pruning) and **no healthchecks.io ping** (a staging run must never mark prod's check seen); the staging batch label `checktick.io/staging-db-client` isolates both directions from the prod `checktick.io/db-client` grant; `STAGING_DATABASE_URL` (checktick-secrets) + `STAGING_SITE_URL` (config overlay) split the environments; `ingress.local.yaml` re-pointed `staging.checktick.uk` → staging Service (cert unchanged); seeded via `checktick-staging-predeploy` (distinct name from the prod pre-deploy Job the workflow manages) and rolled to 0.27.0 matching prod — healthz green end-to-end via service AND ingress, prod unaffected. Capacity measured ~600 Mi steady / 1.5 GiB requests vs ~2–2.8 GiB actually free per node — no resize. Files: `k8s/staging-*.yaml` (out-of-band, NOT in kustomization.yaml), runbook `k8s/README.md` → Staging environment | A pre-prod mirror for releases plus anti-bot signup hygiene on staging, without cross-environment contamination of the database, the shared Graph mailbox or the healthchecks.io checks | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Live web Deployment env patch retired — ALLOWED_HOSTS manifest-pure again**: the interim `k8s/scratch-allowhosts-patch.yaml` (public hosts inline in the Deployment env, the pre-0.25.0 stopgap) retired per the documented sequence — overlay verified (`ALLOWED_HOSTS_EXTRA` carries both public hosts), `web.yaml` re-applied with the LIVE tag sed-substituted (a plain apply would have three-way-merged the image BACKWARDS: manifest pin 0.25.3 vs last-applied 0.24.2 vs live 0.27.0), both hostnames verified green through the ingress, scratch file deleted. The placement hazard recurred exactly as documented — the rollout left BOTH replicas on one node (topology spread is scheduling-time only) — fixed with the cordon dance (cordon → delete one pod → replacement Ready on the other node → uncordon); steady state one web pod per node, nodes 42%/54%. Also refined the "re-apply scratch patches after any manifest re-apply" rule: kubectl-patch-ADDED fields (the affinity pins) SURVIVE applies — only apply-managed field VALUES get reverted (the env entry) | The overlay is now the single source of public hostnames — the manifest env entry can never 400 the public site, and the last cutover-era live-state divergence from the repo is gone | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Deploy (Civo) workflow now deploys staging too**: new `deploy-staging` job (`needs: deploy`) runs the staging migrate Job (tag-substituted), rolls `deploy/checktick-staging-web` (readiness-gated), smoke-checks the staging service, then re-images `prune-unconfirmed-users-staging`; the prod job's roll-every-CronJob step now SKIPS the staging cron so it only moves after the staging schema is migrated (closes the version-skew window where the cron could run a tag the staging DB hadn't migrated to). Failure semantics deliberate: a staging failure never triggers the prod rollback (separate job), and with `maxUnavailable: 0` a failed staging rollout leaves the previous tag serving. No `environment:` gate on the staging job — the `civo` environment approval on the prod job already gates the dispatch, and `CIVO_KUBECONFIG` is a repo-level secret (one approval per release, not two) | Staging is a pre-prod mirror: it must track releases automatically and in the correct order (migrate → web → cron), without staging ever being able to break or roll back prod | Dr Simon Chapman (CTO) | ✅ Active |
| 08/11/2026 | Dr Simon Chapman | **Vault-snapshot CI skip was a silent no-op — the incident RECURRED on the 0.27.1 deploy, found + fixed within the hour**: the roll-every-CronJob step's case patterns (`cronjob/vault-snapshot`, `cronjob/prune-unconfirmed-users-staging`) never matched `kubectl get cronjobs -o name` output (`cronjob.batch/<name>` — resource.group format), so both skips silently no-op'd. The 0.27.1 deploy (13:19 UTC — the first deploy since the vault-snapshot skip was added that morning) rolled vault-snapshot's `upload` container to the app image again, recreating the 03:45 "aws: not found" failure mode, and rolled the staging cron ~2 min BEFORE the staging DB was migrated (the exact version-skew the skip was added to prevent — harmless this release, 0.27.1 ships no migrations). Fixes: live `upload` image restored to `amazon/aws-cli:latest` before the 03:45 run; both patterns changed to globs (`*/vault-snapshot`, `*/prune-unconfirmed-users-staging`). Lesson recorded in the workflow comment and ops doc: a skip that has never fired is untested — grep the roll step's log for the `Skipping` lines on the first deploy after adding one | Nightly Vault escrow freshness is the control that keeps post-snapshot survey creation decryptable after a total Vault loss; CI must skip out-of-band CronJobs and the skip must actually MATCH | Dr Simon Chapman (CTO) | ✅ Active |

#### 2026-11-03 — Cutover driver: Northflank security incident (30 October 2026)

The migration was driven by a **serious security incident disclosed by Northflank on 30 October 2026**
(status page: <https://status.northflank.com/cmvv0rn5a092f14rutwccodpp>):
an attacker accessed **secrets held in Northflank's control plane**, with Northflank's guidance that
**customers should assume all environment variables have been decrypted** and rotate all secrets
immediately; several customers reported unauthorised use of AI provider credentials. Northflank
reported running workloads and workload data as unaffected.

**Response taken (per the migration runbook, `docs/migration-northflank-to-civo.md`):**

1. **Immediate credential rotation (runbook Phase 2, complete 2026-11-02):** every
   provider-level credential that ever transited Northflank's secret store was rotated at its
   provider (OIDC client secrets, `LLM_API_KEY`, `EXTERNAL_DATASET_API_KEY`, `TRUD_API_KEY`,
   `EMAIL_HOST_PASSWORD`, `HCAPTCHA_SECRET`, `LOGS_KEY`, GoCardless API/webhook secrets, Civo DB
   password, Vault AppRole) and re-proven working (healthz-gated rollouts; live Microsoft Graph
   token fetch). Two items were deliberately deferred to the cutover window itself: a new Django
   `SECRET_KEY` (rotated inside the T+0 write freeze — rotating early would have invalidated live
   sessions) and a fresh AppRole on the migrated Vault (minted during the T+5 root ceremony).
2. **Provider migration (this entry):** production hosting moved to Civo Kubernetes
   (London, UK) — UK-sovereign infrastructure for this medical application. Northflank is
   retained stopped (not deleted) until the 48-hour rollback window closes.

`PLATFORM_CUSTODIAN_COMPONENT` was never present in any environment (the custodian component
stays with the custodians out of band per the F6 split-knowledge control), and Vault unseal
shares never transited Northflank.

#### 2026-11-03 — Northflank → Civo production cutover window (timings, UTC)

| Time | Runbook phase | Measured |
| :--- | :--- | :--- |
| 22:05 | T+0 — freeze: Northflank web service paused; 13 Civo CronJobs suspended; Northflank scheduled jobs confirmed silent for the window (daily schedules only) | — |
| 22:05 → 22:09 | T+2 — Vault storage archived, transferred, sha256-verified end to end | ~4 min |
| 22:09 → 22:26 | T+5 — storage restored into the Civo Vault (wiped POC copy first; `file/`-prefix layout normalised), unsealed with 3-of-4 shares, root ceremony (policy + AppRole + revoke) | ~17 min incl. operator steps |
| 22:33 → 22:35 | T+10 — `pg_dump` 2s (1.2 MB compressed, frozen source PG 16.14), `pg_restore` 10s (16 → 17), 78 tables exact count match, `migrate --check` 11s clean | ~2.5 min |
| 22:35 → 22:41 | T+20 — `SITE_URL` flipped, `SECRET_KEY` rotated, pre-deploy job clean, web rollout (readiness-gated) | ~6 min |
| 22:43 → 22:46 | T+25 — smoke gate: 19/19 incl. decrypt round-trip through the migrated Vault; public `/healthz` ok; hashed static asset 200 | ~3 min |
| ~22:46 → 22:50 | T+30 — DNS flip (operator, Namecheap); Let's Encrypt certificate for `checktick.uk` issued ~2 min after the flip; CronJobs resumed | ~4 min |
| 22:53 | Post-flip verification — first 5-minute CronJob completed against production data; site confirmed rendering at `https://checktick.uk` | — |

Announced window was ~30 min (longest rehearsal + 50% contingency per runbook Appendix B);
actual freeze-to-serving was ~45 min including operator handoffs and DNS propagation edge effects.
| Apr 2026 | Dr Simon Chapman | Microsoft Entra app registration created with Mail

### 2d. Application Dependency Maintenance (Non-Security)

Use this section for routine dependency/library updates where no specific CVE or security advisory is being remediated. Security remediations must be recorded in the vulnerability patch log.

| Date | Requestor | Change Description | Business Justification | Approved By | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 09/05/2026 | Dr Simon Chapman | Added split logging policy: non-security dependency updates tracked here; CVE/security remediations tracked in vulnerability patch log | Improve audit clarity by separating maintenance updates from security incidents | Dr Serena Haywood (SIRO) | ✅ Active |
| 14/06/2026 | Dr Simon Chapman | Updated self-hosted axe-core (4.12.0 -> 4.12.1) and regenerated SHA-384 SRI (sha384-JQegRXq6EhTiWoGPFDmqbJNsDow5BoSsGhnaeDzGp+qyOFCuMZZ24qY2fz3FxZF5) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 14/06/2026 | Dr Simon Chapman | Updated self-hosted redoc (2.5.2 -> 2.5.3) and regenerated SHA-384 SRI (sha384-xiEssMQFSpSfLbzRZCGfxxIM5QDb2DTrU6vyoZdp2sV1L6pmOMy6MpTtUoLbpC96) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 02/07/2026 | Dr Simon Chapman | Refreshed self-hosted axe-core 4.12.1 from npm and regenerated SHA-384 SRI (sha384-JQegRXq6EhTiWoGPFDmqbJNsDow5BoSsGhnaeDzGp+qyOFCuMZZ24qY2fz3FxZF5) | Routine JavaScript dependency maintenance for WCAG 2.2 testing support (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |
| 11/08/2026 | Dr Simon Chapman | Updated self-hosted axe-core (4.12.1 -> 4.13.0) and regenerated SHA-384 SRI (sha384-jzJDdyy7z7+/I7TeoAg0Gc8k9hD8b1xRN0W18hMptWJ0cdoiebywhPpCyP9eBOgn) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 30/09/2026 | Dr Simon Chapman | Updated self-hosted htmx.org (2.0.10 -> 2.0.11) and regenerated SHA-384 SRI (sha384-2OatzQy1H+Zd/IIrjr1TcuDGqLXeHhbooAyJY1KdQMKnr4LZ22k31GBLdYKHmVjg) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 30/09/2026 | Dr Simon Chapman | Updated self-hosted redoc (2.5.3 -> 2.5.4) and regenerated SHA-384 SRI (sha384-w447zOpYfw/1Tv/5AK9NfHTlQIqE3RVR6KY62jCyy9zNDgO64cMwGGP1Fj0zJVf5) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 08/10/2026 | Dr Simon Chapman | Updated self-hosted axe-core (4.13.0 -> 4.14.0) and regenerated SHA-384 SRI (sha384-lFUXB8tI4BaTE1bqxH9eeAXON2NH1qsdAhs7S5L++nUNP5QOy+hwr0C3TYEJUEl0) | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |

| 23/10/2026 | Dr Simon Chapman | Updated self-hosted redoc (2.5.4 -> 3.0.1) and regenerated SHA-384 SRI (sha384-j07qRKHNNmcwU1/Y1elJc7pDLHXP/QfbQXTtSkbOJ7uYGJikqAzsFVbY2zR9FqOT). Major version bump: redoc 3.x ships as ESM-only module; updated redoc.html template to use `<script type="module">` to avoid SyntaxError on `export` statement. The `<redoc spec-url>` auto-init pattern is preserved in 3.x via querySelector. | Routine JavaScript dependency maintenance (no CVE remediation referenced) | Dr Serena Haywood (SIRO) | ✅ Active |
