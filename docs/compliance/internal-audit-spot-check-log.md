---
title: "Internal Audit & Spot Check Log"
category: dspt-5-process-reviews
---

# Internal Audit & Spot Check Log

**Date of Audit:** 29/03/2026
**Auditors:** Dr Serena Haywood (SIRO) & Dr Simon Chapman (CTO)

## 1. Audit Scope

To verify that CheckTick is operating in accordance with the board-approved Data
Protection policies and the 10 NHS Data Security Standards, and that all
operational security controls are functioning as intended.

## 2. Checklist & Results

| Control Area | Check Performed | Status | Findings / Actions |
| :--- | :--- | :--- | :--- |
| **User Access** | Reviewed GitHub & Northflank user lists. Confirmed all accounts belong to named current staff with MFA active. No dormant or unrecognised accounts identified. | ✅ Pass | All accounts belong to current staff. MFA confirmed active on all administrative accounts. Zero exceptions. |
| **Encryption** | Tested a database record to verify it is unreadable without the Data Encryption Key (DEK). Confirmed AES-256-GCM is active on all survey fields. | ✅ Pass | AES-256-GCM confirmed active. HashiCorp Vault unsealed and responding normally. |
| **Staff Awareness** | Spot check: both staff asked to locate the Incident Response Plan and describe the first steps in a data breach scenario. | ✅ Pass | Both staff located the IRP in under 30 seconds and correctly described the initial containment and reporting steps. |
| **Backups** | Verified last automated backup completed successfully. Confirmed retention policy is enforced and restoration test log is current. | ✅ Pass | Last backup successful. Retention policy (30 days) enforced. Most recent restoration test passed. |
| **Individual Rights** | Reviewed the SAR Log and Data Rights Request Tracker for any open or overdue requests. | ✅ Pass | Zero requests pending. Tracker is current and ready. |
| **Vulnerability & Patch Status** | Reviewed Vulnerability & Patch Log. Confirmed CI/CD pipeline is blocking on any detected vulnerability. Reviewed active exceptions. | ⚠️ Monitor | One active exception: `pygments` CVE-2026-4539 (local-access-only ReDoS, no fix available upstream). Not network-exploitable. Logged and under monthly review. All other dependencies at zero vulnerabilities. Pipeline blocking active. |
| **Recent Patches Applied** | Confirmed recent security patches deployed: `cryptography` 46.0.5→46.0.6 (CVE-2026-34073), `requests` 2.32.5→2.33.0 (CVE-2026-25645), CSP `base-uri` hardening (AD10), Django admin path hardening (AD11). | ✅ Pass | All patches verified deployed to production. No outstanding critical or high severity vulnerabilities. |
| **Third-Party Access** | Confirmed no active third-party or temporary privileged access grants are in place. | ✅ Pass | Zero active third-party access grants. No temporary credentials outstanding. |
| **MFA Compliance** | Confirmed MFA is enforced on all administrative accounts across GitHub, Northflank, and business email. | ✅ Pass | MFA active on all accounts. Zero exceptions logged. |

## 3. Actions Arising

| # | Observation | Action Required | Owner | Deadline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `pygments` CVE-2026-4539 — no upstream fix available. Local-access-only ReDoS vulnerability in `AdlLexer`. Not network-exploitable. | Monitor PyPI for patched release. Exception to be reviewed monthly. Remove exception immediately when fix is published. | Dr Simon Chapman (CTO) | Review by 27/04/2026 | 🟡 Open — monitoring |

## 4. Previous Actions: Verification of Closure

| Previous Finding | Action Taken | Verified Closed |
| :--- | :--- | :--- |
| `ggshield` transitive vulnerabilities (9 CVEs via GHSA) | Isolated `ggshield` to pre-commit environment, removing from production dependency tree | ✅ 18/01/2026 |
| `python-jose` / `ecdsa` vulnerability (CVE-2024-23342) | Removed `python-jose` entirely; JWT now via `djangorestframework-simplejwt` | ✅ 18/01/2026 |
| `urllib3` multiple CVEs (5 CVEs) | Removed dependency pin; updated to latest | ✅ 18/01/2026 |
| Django critical security update (4 CVEs including SQL injection) | Upgraded Django 5.1.x → 5.2.11 | ✅ 04/02/2026 |
| `cryptography` ECDSA validation bypass (CVE-2026-26007) | Upgraded 46.0.3 → 46.0.5 | ✅ 10/02/2026 |

---

**Approved By:** Dr Serena Haywood, SIRO
**Date of Approval:** 29/03/2026
**Next Scheduled Audit:** September 2026
