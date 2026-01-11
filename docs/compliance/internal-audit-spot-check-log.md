---
title: "Internal Audit & Spot Check Log"
category: dspt-5-process-reviews
---

# Internal Audit & Spot Check Log

**Date of Audit:** [Insert Date]
**Auditors:** {{ siro_name }} (SIRO) & {{ cto_name }} (CTO)

## 1. Audit Scope

To verify that {{ platform_name }} is operating in accordance with the board-approved Data Protection policies and the 10 Data Security Standards.

## 2. Checklist & Results

| Control Area | Check Performed | Status | Findings / Actions |
| :--- | :--- | :--- | :--- |
| **User Access** | Reviewed GitHub & Northflank user lists. | ✅ Pass | All accounts belong to current staff; MFA is active. |
| **Encryption** | Tested a database record to ensure it is unreadable without the DEK. | ✅ Pass | AES-256-GCM confirmed active on survey fields. |
| **Staff Awareness** | Random question: "Where is the Incident Response Plan?" | ✅ Pass | Both staff can locate the IRP in <30 seconds. |
| **Backups** | Verified the last automated backup was successful. | ✅ Pass | Success; retention policy enforced (30 days). |
| **Individual Rights** | Checked [SAR Log](/compliance/data-rights-request-tracker/) for open items. | ✅ Pass | Zero requests pending; tracker is ready. |

## 3. Actions Arising

* **Observation:** One Python library was flagged by Dependabot during the audit.
* **Action:** {{ cto_name }} to patch to version X.X.X by end of week.
* **Owner:** {{ cto_name }}
* **Deadline:** [Insert Date]

---
**Approved By:** {{ siro_name }}, SIRO
