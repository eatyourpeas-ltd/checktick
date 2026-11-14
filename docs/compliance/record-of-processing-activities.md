---
title: "Record of Processing Activities"
category: dspt-1-confidential-data
---

# Record of Processing Activities (ROPA)

**Date of Last Review:** [Insert Date]
**Data Controller:** {{ platform_name }} Ltd
**Data Protection Officer:** {{ dpo_name }}

| Data Subject Category | Data Categories Held | Purpose of Processing | Legal Basis (UK GDPR) | Retention Period |
| :--- | :--- | :--- | :--- | :--- |
| **Healthcare Staff** | Name, Work Email, Role, Organisation, Login Audit Logs. | Platform access, audit trailing, and user management. | **Contract:** Necessary for the performance of our contract with the Trust. | Until account is deactivated + 2 years. |
| **Patients** | Survey responses, Patient ID (e.g. MRN), Demographic data (if collected). | To provide survey results to clinicians for care delivery. | **Health/Social Care:** Article 9(2)(h) - Provision of health or social care. | 7 years (per NHS Records Code of Practice). |
| **{{ platform_name }} Staff** | Name, Contact details, Payroll info, Training records. | Employment and HR management. | **Legal Obligation:** Necessary for employment law compliance. | Duration of employment + 6 years. |
| **Website Visitors** | IP address, Browser type (via security logs). | Security monitoring and threat prevention (WAF). | **Legitimate Interest:** Protecting the platform from cyber attacks. | 90 days (Logs). |
| **Appraisees (Clinicians under Appraisal)** | Appraisal feedback about the appraisee (released report snapshots); self-assessment responses (linked to the appraisee via a `self` token); appraisee name as the survey subject placeholder; appraisal cycle and instrument. | Designated-body appraisal (GMC-style 360) for revalidation and professional development, including the self-versus-others comparison in released reports. | **To be confirmed by DPO:** Article 6(1)(c) or (e), and Article 9(2)(b) or (h) where special category data is present. | Per the designated body's appraisal record policy (to be confirmed by DPO). Released snapshots are immutable. |
| **Patient Respondents (Appraisal Feedback)** | Anonymous survey responses about the appraisee. Responses are anonymous by design: no token is issued and no identifiers are collected. Free text may include health information disclosed by the patient. | Collection of patient feedback for the appraisee's 360 appraisal. | **To be confirmed by DPO:** Article 6(1)(e) or (f), and Article 9(2)(h) where health information is disclosed. | As per survey retention settings (to be confirmed by DPO). |
| **Colleague Raters (Nominated for the Cycle)** | Colleague nomination data for the appraisal cycle, used to approve raters and issue tokens. | Pseudonymous colleague feedback for the appraisee's 360 appraisal. | **To be confirmed by DPO:** as for Appraisees. | Nominations are discarded when the appraisal cycle closes. Pseudonymous token references remain with the survey record. |
| **Colleague Raters (Pseudonymous Linkage and Exception Review Disclosure)** | Token-to-response linkage: token, category values, submission metadata, and the submitting user where the response was submitted while logged in. | Identification of a rater only where a response indicates serious risk and a second party has approved an exception review (appraiser raises; RO co-signs). Never shown in routine reporting. | **To be confirmed by DPO:** as for Appraisees; each disclosure must be justified on its own facts. | Disclosure events are recorded in the audit log. Linkage data follows the survey record retention (to be confirmed by DPO). |

## Data Transfers

* **Hosting:** All patient data is stored in the UK (managed Kubernetes on Civo, London region).
* **International Transfers:** None. All processing of health data occurs within the UK.

## Security Measures

All health data is encrypted at rest (AES-256) and in transit (TLS 1.2+). Access is governed by the Access Control Policy and restricted via MFA.

Appraisal survey keys are wrapped with the organisation master key, so the appraisee (as distributor) holds no decryption path. The Responsible Officer can recover an appraisal survey if the appraiser leaves.
