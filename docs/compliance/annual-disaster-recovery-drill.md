---
title: "BCDR Test Plan & Exercise Schedule"
category: dspt-7-continuity
---

# BCDR Test Plan & Exercise Schedule

**Document Status:** Pre-Launch Planning Document
**Last Reviewed:** March 2026
**Owners:** CTO & SIRO

## 1. Purpose

This document defines the planned Business Continuity and Disaster Recovery
(BCDR) test programme for {{ platform_name }}. As {{ platform_name }} is
currently in pre-production, a full end-to-end restoration drill against
live clinical data has not yet been conducted. This is documented as an
open pre-launch action in the Business Continuity and Disaster Recovery Plan.

A full BCDR test will be completed and documented prior to live clinical
deployment. This document records completed partial tests, defines the
scenario and success criteria for the full pre-launch test, and sets out
the ongoing annual test schedule.

## 2. Completed Tests (Development Environment)

### Test CT-01: Vault Unseal and Platform Key Reconstruction
**Date:** March 2026
**Environment:** Development
**Conducted by:** {{ cto_name }} (CTO)

**Scenario:** Full Vault unseal workflow using YubiKey hardware tokens,
followed by reconstruction of the platform master key from Shamir custodian
shares.

**Configuration tested:**
- 2 YubiKeys each holding 2 unseal keys and 2 shares of the platform
  custodian component
- 2 YubiKey backups held at separate secure locations
- Shamir threshold: 3 of 4 shares required to reconstruct the platform key

**Steps completed:**

| Step | Result |
| :--- | :--- |
| Vault unseal using YubiKey hardware tokens | ✅ Pass |
| Platform custodian component reconstruction from Shamir shares | ✅ Pass |
| Vault health check post-unseal | ✅ Pass |
| Full end-to-end key derivation workflow | ✅ Pass |

**Outcome:** The complete Vault unseal and platform key reconstruction
workflow was validated in a development environment. YubiKey hardware
tokens functioned correctly as the physical bearer of both unseal keys
and custodian shares. No issues identified. The workflow is confirmed
viable and documented in the Vault Integration guide.

**Limitations:** This test was conducted in a development environment
against test data only. A full test against a production-equivalent
snapshot, including database restoration and end-to-end survey
decryption, is planned prior to live deployment (see Section 4).

---

## 3. Planned Full BCDR Test (Pre-Launch)

**Scenario:** Simulated complete infrastructure loss — Vault data corruption
and PostgreSQL database failure requiring full restoration from Northflank
snapshots.

**Participants:** {{ siro_name }} (SIRO), {{ cto_name }} (CTO)

**Target Completion:** Prior to live clinical deployment

### Test Objectives

1. Restore PostgreSQL database from most recent Northflank managed addon
   snapshot into a clean staging environment
2. Redeploy the application container from GitHub into the staging environment
3. Restore the Vault persistent volume from Northflank snapshot and unseal
   using YubiKey hardware tokens (as validated in CT-01)
4. Reconstruct platform master key from Shamir custodian shares held on
   YubiKeys (as validated in CT-01)
5. Verify that an existing test user account can successfully authenticate
   and decrypt a test survey record end-to-end
6. Confirm total simulated recovery time is within the 4-hour RTO target

### Success Criteria

| Step | Target Time | Pass Criteria |
| :--- | :--- | :--- |
| DB Restoration | < 60 mins | Application connects and data readable |
| Vault Restore & Unseal | < 30 mins | Vault unsealed and health check passes |
| Platform Key Reconstruction | < 15 mins | Custodian shares reconstructed successfully |
| End-to-End Decryption | < 15 mins | Test survey record successfully decrypted |
| **Total RTO** | **< 4 hours** | **All steps passed within target** |

### Post-Test Actions

Following the test, the CTO and SIRO will:

* Document actual times and results in this report
* Record any improvements identified as actions in the Risk Register
* Update Vault and restoration documentation if any issues are found
* Confirm the next annual test date

---

## 4. Ongoing Test Schedule

Once live clinical deployment is in place, BCDR tests will be conducted
on the following schedule:

| Test Type | Frequency | Owner |
| :--- | :--- | :--- |
| Full restoration drill (DB + Vault + App) | Annually | CTO |
| Database-only snapshot restoration | Quarterly | CTO |
| Vault unseal and key reconstruction verification | Annually | CTO |
| Emergency contact and YubiKey location review | Quarterly | SIRO |
| Tabletop walkthrough of communication plan | Annually | CTO & SIRO |

---

## 5. Test History

| ID | Date | Type | Environment | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| CT-01 | March 2026 | Vault unseal & platform key reconstruction | Development | ✅ Pass |
| CT-02 | Pre-launch TBC | Full restoration drill | Staging | Pending |
