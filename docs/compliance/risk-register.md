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
| **R02** | Supply Chain: Civo Outage | Availability | 2 | 4 | **8** | Daily off-site backups; BCDR plan tested annually. | {{ cto_name }} |
| **R03** | Supply Chain: GitHub/Code Breach | Integrity | 1 | 4 | **4** | Mandatory GPG signed commits; MFA; Branch protection. | {{ cto_name }} |
| **R04** | Insider Threat (Staff Error) | Security | 2 | 3 | **6** | Annual NHS Training; Least Privilege access; Audit logs. | {{ siro_name }} |
| **R05** | Loss of Staff Laptop | Physical | 2 | 3 | **6** | Full Disk Encryption; Remote wipe capability; No local DB. | {{ cto_name }} |
| **R06** | Supply Chain: GoCardless Breach | Financial | 1 | 3 | **3** | No banking data stored locally; Rely on provider PCI-DSS. | {{ siro_name }} |
| **R07** | Application-Layer Vulnerabilities (Aug 2026 review) | Security | 1 | 4 | **4** | 18 findings (F1–F18) identified in static review: 2 High, 6 Medium, 9 Low, 1 Info. All 18 findings resolved (01–02/08/2026) with regression tests. See `security-review-august-2026.md` and `security-review-log.md`. | {{ cto_name }} |
| **R08** | Distributor Role Over-Scoping (appraisal mis-scoped access to results) | Security | 2 | 4 | **8** | DISTRIBUTOR membership excluded from `can_view_survey`; appraisee holds no key path (org-key wrap); token and completion-count access only; tier-gated; membership changes audit-logged; RBAC negative tests. | {{ cto_name }} |
| **R09** | Exception Review Misuse (rater identity disclosed without RO co-signature) | Security | 2 | 4 | **8** | Default reporting never shows token-to-response linkage; RO co-signature by a user other than the raiser required; raise, approve, and reject audit-logged (approval at WARNING); released report records a count only. | {{ siro_name }} |
| **R10** | Appraiser Turnover: Org-Key Handling on Recovery | Availability | 2 | 3 | **6** | Survey keys wrapped with the organisation master key (no personal-key-only path); RO recovers and re-wraps to the incoming appraiser; key recovery logged at CRITICAL. | {{ cto_name }} |
| **R11** | Self-Assessment Re-Identification (self token is single-holder and linked to the appraisee) | Security | 2 | 2 | **4** | Report visibility limited to appraisee, appraiser, and RO; self-assessment appears only in released snapshots; no live results access for the appraisee. | {{ cto_name }} |

## Risk Review Frequency

This register is a live document. It is reviewed:

1. **Monthly:** At Founders' Board meetings.
2. **Ad-hoc:** Following any security incident or major infrastructure change.
3. **Annually:** As part of the DSPT submission process.
