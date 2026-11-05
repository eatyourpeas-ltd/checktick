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
