---
title: "Data Protection Impact Assessment (DPIA) Summary"
category: dspt-1-confidential-data
---

# Data Protection Impact Assessment (DPIA) Summary

**Project:** {{ platform_name }} Health Survey Platform
**Date:** 29/12/2025
**Lead:** {{ siro_name }}

### 1. Description of Processing

{{ platform_name }} processes health-related survey data on behalf of healthcare providers. Data is collected via web forms, encrypted in transit (TLS), and stored encrypted at rest (AES-256).

### 2. Necessity and Proportionality

Processing is limited to the minimum data required for the survey creator's specific health goal. Our auto-deletion policy (6-24 months) ensures we do not hold data longer than necessary.

### 3. Risk Assessment & Mitigation

| Risk Identified | Level | Mitigation |
| :--- | :--- | :--- |
| **Unauthorized Access** | High | Role-Based Access Control (RBAC), MFA for admins, and Scoped API keys. |
| **Data Breach in Transit** | Med | Strict TLS 1.2+ requirement; no insecure HTTP allowed. |
| **Loss of Encryption Keys** | Med | Distributed Vault Unseal keys and documented recovery procedures. |
| **Server Failure** | Low | Nightly encrypted base backups with continuous WAL archiving to Civo Object Storage, UK London region (RPO 24 hours); RTO < 4 hours. |

### 4. Outcome

The residual risk is considered **Low**. All processing is conducted within the UK, and high-level encryption is applied at every stage of the data lifecycle.

### 5. Addendum: Appraisal Processing (GMC-Style 360)

**Addendum Date:** 14/11/2026
**Feature:** Appraisal workflow (branch `feat/appraisal-workflow`)

**Description of Processing.** Designated bodies (for example, hospital appraisal departments) run GMC-style 360 appraisals on the platform. Each appraisee has one survey per appraisal cycle. Feedback is collected from anonymous patients, from pseudonymous colleague raters holding tokens, and from the appraisee's own self-assessment. Released reports are shared with the appraisee and the Responsible Officer. This processing includes special category context: feedback may contain health information disclosed by patients, and professional performance data about a named clinician. Controller and processor roles for appraisal data are to be confirmed by the DPO against the designated body's agreement.

**Necessity and Proportionality.** Patient respondents are anonymous and hold no token. Colleague raters are pseudonymous. Identification occurs only through the two-party exception review described below. Released reports show counts and percentages per rater population, with populations below the minimum-response threshold (default 5) suppressed. Colleague nominations are cycle-scoped.

**Identified-Rater Disclosure.** Reporting never shows token-to-response linkage by default. Disclosure requires an exception review raised by the appraiser and co-signed by the Responsible Officer, who must be a different user from the raiser. Raise, approve, and reject are audit-logged, with approval (disclosure) at Warning severity. The appraisee never sees exception reviews.

| Risk Identified | Level | Mitigation |
| :--- | :--- | :--- |
| **Special category data (health and professional performance)** | High | Organisation-scoped access; survey responses encrypted at rest with organisation-key wrap; released reports visible only to the appraisee, appraiser, and Responsible Officer; Article 9 condition to be confirmed by the DPO. |
| **Identified-rater disclosure without justification** | Med | Linkage hidden from default reporting; two-party control (RO co-signature by a different user); raise, approve, and reject audit-logged; released report records a count only. |
| **Distributor mis-scoped access to results** | Med | DISTRIBUTOR membership excluded from results access; appraisee holds no key path; token and completion-count access only; membership changes audit-logged. |
| **Retention of colleague nominations** | Low | Nominations are cycle-scoped and discarded at cycle close, leaving pseudonymous token references only. |
| **Appraiser turnover and key recovery** | Low | Survey keys wrapped with the organisation master key; Responsible Officer recovers and re-wraps to the incoming appraiser; key recovery logged at Critical severity. |
| **Self-assessment re-identification** | Low | Self token is single-holder and linked to the appraisee by design; report visibility limited to the appraisee, appraiser, and Responsible Officer. |

**Retention.** Colleague nominations are discarded when the appraisal cycle closes. Pseudonymous token references and released report snapshots are retained for the appraisal record period, which the DPO must set. Until then, the platform auto-deletion policy (6-24 months) is assumed to apply; this is to be confirmed.

**Outcome.** This addendum assesses residual risk as **Medium** for identified-rater disclosure, reduced from High by the two-party control and audit trail, and **Low** for the remaining risks. This is an assessment only and requires SIRO and DPO sign-off before live appraisals begin.
