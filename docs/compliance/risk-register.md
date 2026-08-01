---
title: "Data Security & Protection Risk Register"
category: dspt-5-process-reviews
---

# Data Security & Protection Risk Register

**Owner:** {{ siro_name }} (SIRO) | **Reviewed:** [Monthly]

## Risk Scoring Matrix

* **Likelihood:** 1 (Rare) to 5 (Almost Certain)
* **Impact:** 1 (Negligible) to 5 (Catastrophic)
* **Total Risk:** Likelihood x Impact

| ID | Risk Description | Category | L | I | Total | Mitigation Strategy | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R01** | Unauthorized DB Access | Security | 2 | 5 | **10** | AES-256-GCM encryption; MFA for all admins; Private VPC. | {{ cto_name }} |
| **R02** | Supply Chain: Northflank Outage | Availability | 2 | 4 | **8** | Daily off-site backups; BCDR plan tested annually. | {{ cto_name }} |
| **R03** | Supply Chain: GitHub/Code Breach | Integrity | 1 | 4 | **4** | Mandatory GPG signed commits; MFA; Branch protection. | {{ cto_name }} |
| **R04** | Insider Threat (Staff Error) | Security | 2 | 3 | **6** | Annual NHS Training; Least Privilege access; Audit logs. | {{ siro_name }} |
| **R05** | Loss of Staff Laptop | Physical | 2 | 3 | **6** | Full Disk Encryption; Remote wipe capability; No local DB. | {{ cto_name }} |
| **R06** | Supply Chain: GoCardless Breach | Financial | 1 | 3 | **3** | No banking data stored locally; Rely on provider PCI-DSS. | {{ siro_name }} |
| **R07** | Application-Layer Vulnerabilities (Aug 2026 review) | Security | 2 | 4 | **8** | 17 findings (F1–F17) identified in static review: 2 High, 6 Medium, 8 Low, 1 Info. F1, F2, F6, and F12 resolved on 01/08/2026 with regression tests; 13 findings remain open. Continue remediation via atomic PRs. See `security-review-august-2026.md`. | {{ cto_name }} |

## Risk Review Frequency

This register is a live document. It is reviewed:

1. **Monthly:** At Founders' Board meetings.
2. **Ad-hoc:** Following any security incident or major infrastructure change.
3. **Annually:** As part of the DSPT submission process.
