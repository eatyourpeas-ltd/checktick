---
title: "Backup Restoration Test Log"
category: dspt-7-continuity
---

# Backup Restoration Test Log (Evidence 7.3.5)

**Policy Requirement:** Full system restore test conducted at least annually.
**{{ platform_name }} Standard:** Quarterly restoration drills (once in production).
**Current Status:** Pre-production. Full end-to-end restoration drill scheduled
as a mandatory pre-launch action.

---

## Test Log

| ID | Date | Type | Scenario | Environment | Result | Time Taken | Verified By |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CT-01 | March 2026 | Partial — Vault unseal & key reconstruction | Simulated Vault loss requiring unseal and platform master key reconstruction from Shamir custodian shares via YubiKey hardware tokens | Development | ✅ Pass | < 30 mins | {{ cto_name }} |
| CT-02 | Pre-launch TBC | Full system restore | Simulated complete infrastructure loss — DB + Vault + App redeployment | Staging | ⏳ Pending | — | — |

---

## CT-01 Detail: Vault Unseal & Platform Key Reconstruction
**Date:** March 2026
**Environment:** Development
**Conducted by:** {{ cto_name }} (CTO)

**Scope:** Validated the complete Vault unseal and platform master key
reconstruction workflow using YubiKey hardware tokens. This is the most
technically complex component of the full restoration procedure and a
prerequisite for any encrypted data recovery.

**Configuration:**
- 2 YubiKeys each holding 2 unseal keys and 2 shares of the platform
  custodian component
- 2 YubiKey backups stored at separate secure locations
- Shamir threshold: 3 of 4 shares required to reconstruct the platform key

**Steps completed:**

| Step | Result | Notes |
| :--- | :--- | :--- |
| Vault unseal using YubiKey hardware tokens | ✅ Pass | Both primary YubiKeys tested |
| Platform custodian component reconstruction from Shamir shares | ✅ Pass | Threshold met with 3 of 4 shares |
| Vault health check post-unseal | ✅ Pass | All secrets accessible |
| Full end-to-end key derivation workflow | ✅ Pass | Survey KEK successfully derived |

**Outcome:** Workflow confirmed viable. No issues identified.

**Limitations:** Development environment only, against test data.
Full end-to-end test including database restoration and survey
decryption is planned pre-launch (CT-02).

---

## CT-02 Plan: Full System Restoration Drill
**Target Date:** Prior to live clinical deployment
**Environment:** Staging

**Scope:** Full end-to-end system restoration from Northflank snapshots,
covering all components required to restore the essential service.

**Steps planned:**

| Step | Target Time | Pass Criteria |
| :--- | :--- | :--- |
| Restore MFA-protected admin access to Northflank and GitHub | < 15 mins | Console accessible |
| Restore Vault volume from Northflank snapshot | < 20 mins | Vault service running |
| Unseal Vault using YubiKey tokens (as per CT-01) | < 15 mins | Vault unsealed, health check passes |
| Restore PostgreSQL from Northflank addon snapshot | < 60 mins | Database accessible |
| Redeploy application container from GitHub | < 20 mins | Application boots successfully |
| Verify DNS resolution and platform reachability | < 10 mins | Platform responding on expected domain |
| End-to-end decryption of test survey record | < 15 mins | Test record successfully decrypted |
| **Total RTO** | **< 4 hours** | **All steps passed within target** |

**Results:** To be completed and documented here prior to go-live.

---

## Pre-Production Statement

{{ platform_name }} is currently in pre-production. No clinical patient
data is held at this time. CT-01 confirms the most critical recovery
component — Vault unseal and key reconstruction — has been successfully
validated in a development environment using production-equivalent
YubiKey hardware and Shamir key distribution.

CT-02 (full system restoration drill) is a mandatory documented
pre-launch action and will be completed and recorded here before
any health data is processed.

**Next scheduled review:** Upon completion of CT-02, or June 2026,
whichever is sooner.
