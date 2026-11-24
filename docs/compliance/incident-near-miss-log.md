---
title: "Incident & Near-Miss Log"
category: dspt-6-incidents
---

# Incident & Near-Miss Log (2025-2026)

**Owner:** {{ siro_name }} (SIRO)
**Review Frequency:** Quarterly

---

## 1. Summary Table

| ID | Date | Type | Severity | Description | Action Taken | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| NM-01 | 21/01/2026 | Near-Miss | Low | Automated scan detected an outdated dependency (axe-core). | Updated axe-core 4.10.2 → 4.11.0 and merged via PR. | Closed |
| NM-02 | 01/08/2026 | Near-Miss | High | Web recovery console (`recovery_execute`) reads removed `PLATFORM_CUSTODIAN_COMPONENT` setting, bypassing the 3-of-4 Shamir custodian-share control. Either crashes (DoS on recovery) or allows single-superuser KEK recovery without custodian shares. | Removed web execution; recovery now requires 3 of 4 shares through the management command, and the legacy environment setting is rejected. | Closed |
| NM-03 | 01/08/2026 | Near-Miss | High | SVG upload in survey builder image-choice questions (`_validate_and_process_image`) allows stored XSS via direct `/media/` navigation. SVG files skip sanitisation and execute embedded scripts in the CheckTick origin. | Removed SVG upload support, added script-bearing SVG and animation regression tests, and confirmed no legacy SVG records or files existed in production media. | Closed |
| INC-01 | 05/11/2026 | Incident (availability) | Low | Site returned 503s for several minutes while the Vault was sealed for the interim backup window: readiness probes pointed at the deep `/healthz` (which fails on a sealed Vault), draining all Service endpoints. No data accessed, lost, altered or exposed. | Probe separation: startup/liveness pinned to the trivial `/api/health`, readiness kept deep on `/healthz`; seal ceremonies treated as availability windows (`k8s/web.yaml` design notes). | Closed |
| INC-02 | 08/11/2026 | Incident (availability) | Low | ~8 min site unavailability (~17:40–17:51 UTC) during the 0.28.1 deploy window: Civo API-server connection loss broke the deploy workflow's CronJob-roll step (firing a rollback against a healthy deployment), and the replaced web pods — both converged onto ONE node by the roll — flapped through containerd create-errors. No data accessed, lost, altered or exposed. | Web `replicas: 3` + max-weight preferred anti-affinity (manifests), CronJob-roll step retries + degrade-to-warning (workflow), Civo control-plane flakiness reported to Civo support (Supplier Incident Log). Verified on the next deploy: zero-downtime roll, 0 restarts. | Closed |
| INC-03 | 21/11/2026 | Incident (availability) | High | Total site unavailability from 06:35 UTC (ongoing >11h at time of logging): Civo platform-wide network failure affecting ALL regions (LON1, NYC1, FRA1, MUM1, JKT1) — Network components Down while Compute/Storage remained Operational. All TCP connections to the cluster node (74.220.17.170) time out on every port (80/443/6443): traffic never reaches the cluster (timeouts, not 503s; DNS resolution correct) and kubectl is unusable. No data accessed, lost, altered or exposed; data at rest and all backups unaffected. | Detected by StatusCake external monitor — Civo sent no incident notification email; the status page was the only channel. Civo timeline: 06:35 Investigating → 12:26 Identified (~6h, no interim updates) → 17:12 restoration expected progressively within ~2h. Post-recovery checklist prepared (node readiness, web pod placement + coredns replicas, Vault seal check/unseal, /healthz, s/k8s-backup-verify). Hardening escalated: cross-provider UK backup copy, degraded-mode fallback page, second external monitor, DR drill, SLA review + PIR request. See Supplier Incident Log. | Open |

**Production Incidents to date: 3 — all availability-only; zero data accessed, lost, altered or exposed (no data security or protection impact)**
**Near-Misses to date: 3 (3 resolved, 0 open)**

---

## 2. Detailed Near-Miss Records

### Record: NM-01 — Vulnerable Dependency (axe-core)

* **Discovery Date:** 10/01/2026
* **Reporter:** GitHub Dependabot (Automated)
* **Severity:** Low
* **Impact:** None. Vulnerability identified and resolved by automated process
  before any exploitation was possible.
* **Root Cause:** Third-party library released a security patch for a known CVE.
  Automated monitoring detected the outdated version within the standard scan cycle.
* **Corrective Action:** CTO merged the patch and updated `pyproject.toml`.
  Updated SRI hash computed and verified.
* **Verification:** CI/CD pipeline passed with zero security vulnerabilities
  post-merge. Confirmed in Vulnerability & Patch Log.
* **Lessons Learned:** No process change required. Automated detection and
  remediation pipeline functioned as designed. Confirms that the zero-exception
  CI/CD policy is effective at catching dependency vulnerabilities before
  they reach production.

### Record: NM-02 — Web recovery console bypasses Shamir custodian-share control (F6)

* **Discovery Date:** 01/08/2026
* **Reporter:** CTO (security deep-dive review)
* **Severity:** High
* **Impact:** None at time of discovery. The web recovery path was identified
  during static review before any exploitation. No patient data was accessed.
* **Root Cause:** `RecoveryRequest.execute_recovery` (model method) reads the
  removed `PLATFORM_CUSTODIAN_COMPONENT` setting directly, while the documented
  security model requires 3-of-4 Shamir custodian shares via management command.
  The web view `recovery_execute` calls this model method, creating a second
  execution path that bypasses the custodian control.
* **Corrective Action:** Removed the web execution endpoint and routed operators
  to the `execute_platform_recovery` management command. The model method now
  requires a caller-supplied custodian component, and application startup rejects
  `PLATFORM_CUSTODIAN_COMPONENT` in the environment.
* **Verification:** Repository review confirmed there is no web recovery execution
  URL and that the secure management command requires 3 of 4 custodian shares.
* **Lessons Learned:** When a security control is migrated (settings → Shamir
  shares), all code paths that read the old setting must be removed in the same
  change. A commented-out setting is not sufficient — delete it so any deploy
  that sets it fails loudly.

### Record: NM-03 — SVG upload stored XSS via `/media/` (F12)

* **Discovery Date:** 01/08/2026
* **Reporter:** CTO (security deep-dive review)
* **Severity:** High
* **Impact:** None at time of discovery. The vulnerability was identified
  during static review before any exploitation. No patient data was accessed.
* **Root Cause:** `_validate_and_process_image` explicitly allows `.svg` /
  `image/svg+xml` and skips all sanitisation for SVG files. Uploaded SVGs are
  stored unmodified under `/media/` and served same-origin. While `<img src>`
  does not execute SVG scripts, direct navigation to the `/media/` URL renders
  the SVG as a document and executes embedded `<script>` in the CheckTick origin.
* **Corrective Action:** Removed SVG from the survey-image extension/MIME
  allowlists and browser file picker. Added server-side rejection of animated
  variants of allowed raster formats so survey image choices remain static.
* **Verification:** Regression tests pass for rejection of a script-bearing SVG
  and animated PNG without persistence. A production console audit reported
  zero SVG-backed `QuestionImage` records and zero `.svg` files under
  `MEDIA_ROOT`, so no legacy cleanup migration or media-header exception was
  required.
* **Lessons Learned:** SVG is a dual-purpose format (image + document). Allowing
  SVG upload to a same-origin media store is equivalent to allowing HTML upload.
  Image validators should treat SVG as script-capable unless sanitised.

### Record: INC-01 — Vault sealed-window outage (C7)

* **Discovery Date:** 05/11/2026 (live — healthz 503s)
* **Reporter:** CTO
* **Severity:** Low
* **Impact:** Brief (~minutes) site unavailability during the interim Vault
  backup's sealed window. No data accessed, lost, altered or exposed; the
  compliance system of record (`AuditLog`, PostgreSQL) was unaffected.
* **Root Cause:** Readiness probes pointed at the deep `/healthz`, which fails
  while the Vault is sealed — all web pods went NotReady and the Service lost
  its endpoints. Restarts cannot fix a seal, so recovery waited on the unseal.
* **Corrective Action:** Probe separation — startup/liveness on the trivial
  `/api/health`, readiness kept deep on `/healthz`; seal/unseal ceremonies
  documented as planned availability windows (`k8s/web.yaml` design notes).
* **Verification:** Subsequent seal windows (the 06/11 Raft migration and the
  08/11 node-recycle ceremony) caused no readiness-driven outage.
* **Lessons Learned:** A deep health check must never gate liveness/startup —
  it gates TRAFFIC, and only traffic. Vault seal windows are planned downtime
  for availability purposes and must be scheduled accordingly.

### Record: INC-02 — Deploy-window outage: Civo control-plane flakiness + single-node convergence (C7)

* **Discovery Date:** 08/11/2026 ~17:45 UTC (site 503s during the 0.28.1 deploy)
* **Reporter:** CTO
* **Severity:** Low
* **Impact:** ~8 min site unavailability (~17:40–17:51 UTC). No data accessed,
  lost, altered or exposed; `AuditLog` unaffected.
* **Root Cause:** Two compounding failures. (a) The Civo Kubernetes API server
  was intermittently unreachable from external clients from ~16:42 UTC
  (workflow logs: `http2: client connection lost`, `dial tcp 74.220.17.170:6443:
  i/o timeout`) — the deploy workflow's CronJob-roll step failed on that
  transient error, which fired the rollback step against a HEALTHY deployment;
  the rollback also failed on the same API errors. (b) Both web replicas had
  converged onto one node during the roll (topology spread constrains
  scheduling decisions, not the end state), so the pod replacement + containerd
  create-stall window (`failed to reserve container name`, context deadlines)
  removed 100% of serving capacity.
* **Corrective Action:** Web `replicas: 3` (applied live via `kubectl scale`;
  manifest updated), max-weight preferred pod anti-affinity (hostname),
  CronJob-roll step retries 3×/15s and degrades to a loud warning instead of
  failing the deploy, image pins re-bumped 0.27.1 → 0.29.0 so `apply -k` cannot
  regress the image. Civo control-plane flakiness reported to Civo support and
  recorded in the Supplier Incident Log.
* **Verification:** Live poll through the next deploy (0.29.0, 19:53–19:57 UTC):
  zero-downtime roll, 0 restarts, endpoints continuously populated; memory
  ceiling checked before/after the scale-up (busiest node 63% actual / 74%
  requests, ~2.0Gi actual free). Post-roll spread verified and re-balanced.
* **Lessons Learned:** (i) A failing CronJob-tag housekeeping step must never
  roll back a healthy web deployment — housekeeping failure is drift, not
  downtime. (ii) Topology spread constrains scheduling, not the post-roll end
  state — verify spread after every deploy. (iii) With the control plane
  unreachable the Deployment controller cannot replace dead pods: control-plane
  health is part of availability, and supplier API stability is a dependency
  to monitor.

### Record: INC-03 — Civo platform-wide network outage (total site unavailability)

* **Discovery Date:** 21/11/2026 06:35 UTC (ongoing at time of logging, 17:39 UTC)
* **Reporter:** StatusCake external monitor (5-min `/healthz` polling). Civo sent
  no incident notification email — `status.civo.com` was the only channel.
* **Severity:** High (availability) — zero data impact
* **Impact:** Total site unavailability from 06:35 UTC. TCP connections to the
  cluster node (74.220.17.170) time out on all ports (80/443/6443) — traffic
  never reaches the cluster (connection timeouts, not 503s; DNS resolution
  correct throughout). kubectl unusable (API server unreachable). No data
  accessed, lost, altered or exposed; Compute and Storage remained Operational
  per Civo's status page, so data at rest and all backups were unaffected.
* **Root Cause:** Supplier-side: Civo platform-wide network failure affecting
  ALL regions (LON1, NYC1, FRA1, MUM1, JKT1) — Network components Down while
  Compute/Storage stayed Operational; the Civo API and website were also Down.
  No in-cluster measure (replicas, PDBs, probes) can mitigate a provider
  network-layer failure.
* **Civo comms timeline:** 06:35 Investigating → 12:26 Identified (~6h to root
  cause, no interim updates) → 17:12 restoration expected progressively over
  the following ~2 hours.
* **Corrective Action:** In progress. Post-recovery checklist prepared (node
  readiness; web pod placement + coredns 2 replicas per standing hazards;
  Vault seal check + unseal ceremony if any node restarted; `/healthz`;
  `s/k8s-backup-verify`). Hardening escalated in priority: cross-provider UK
  backup copy (all backups currently land in the same Civo LON1 object store —
  see Backup Isolation Procedure); degraded-mode static fallback page served
  from outside Civo; second independent external monitor; DR drill to measure
  a real RTO; SLA review and service-credit claim; PIR requested from Civo.
  Also noted: Civo LON1 maintenance scheduled 23/11/2026 (node restarts →
  planned Vault unseal duty).
* **Verification:** Pending restoration — completion of the post-recovery
  checklist to be recorded here.
* **Lessons Learned:** (i) A provider-region network failure is total for a
  single-region deployment; only multi-site architecture or formally accepted
  risk addresses it. (ii) Triage rule: `/healthz` 503 = our problem (Vault/DB/
  pods); connection timeout = provider problem (check status.civo.com before
  touching the cluster). (iii) Supplier incident notification cannot be
  relied upon — external monitoring was the actual detection path; a second
  independent monitor is required. (iv) Backups held with the same provider
  and in the same region as the cluster do not satisfy backup isolation
  against provider-level failure — cross-provider copies are required.

---

## 3. Statement on Production Incidents

EatYourPeas Ltd confirms that {{ platform_name }} has had **zero production
 data security or protection incidents** since the platform's launch. Three
availability-only incidents are recorded above: INC-01 and INC-02 (brief,
minutes-scale unavailability during infrastructure operations) and INC-03
(an extended supplier-side outage — a Civo platform-wide network failure on
21/11/2026 causing total site unavailability for most of a day). In none of
these was any data accessed, lost, altered or exposed. This is
attributed to:

- Continuous automated vulnerability scanning (pip-audit, Dependabot, CodeQL)
  blocking vulnerable code from reaching production
- Mandatory MFA on all administrative accounts with no exceptions
- Field-level AES-256-GCM encryption ensuring data is protected at rest
- Network isolation of production infrastructure

This statement is reviewed and confirmed at each quarterly SIRO sign-off below.

---

## 4. Quarterly SIRO Sign-off

| Quarter | Incidents | Near-Misses | Notes | Signed |
| :--- | :--- | :--- | :--- | :--- |
| Q3 2025 (Jul–Sep) | 0 | 0 | Platform in pre-launch hardening phase. | {{ siro_name }}, SIRO |
| Q4 2025 (Oct–Dec) | 0 | 0 | No incidents or near-misses. | {{ siro_name }}, SIRO |
| Q1 2026 (Jan–Mar) | 0 | 1 | NM-01 detected and resolved via automated pipeline. | {{ siro_name }}, SIRO |
| Q2 2026 (Apr–Jun) | 0 | 0 | No incidents or near-misses. | {{ siro_name }}, SIRO |
| Q3 2026 (Jul–Sep) | 0 | 2 | NM-02, NM-03 found and fixed via security deep-dive review. | {{ siro_name }}, SIRO |
| Q4 2026 (Oct–Dec) | 3 | 0 | INC-01 (Vault seal window), INC-02 (deploy-window outage), INC-03 (Civo platform-wide network outage, 21/11 — ongoing at time of writing; supplier incident under monitoring). | {{ siro_name }}, SIRO |
