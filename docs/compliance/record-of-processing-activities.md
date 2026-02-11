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

## Data Transfers

* **Hosting:** All patient data is stored in the UK (AWS London Region / Northflank).
* **International Transfers:** None. All processing of health data occurs within the UK.

## Security Measures

All health data is encrypted at rest (AES-256) and in transit (TLS 1.2+). Access is governed by the Access Control Policy and restricted via MFA.
