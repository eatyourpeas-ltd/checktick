---
title: "Information Governance: Roles & Responsibilities"
category: dspt-2-staff-responsibilities
---

# Information Governance: Roles & Responsibilities

**Version:** 1.0
**Effective Date:** [Insert Date]

## 1. Statutory Roles

### Senior Information Risk Owner (SIRO) - {{ cto_name }}

* **Accountability:** Overall ownership of the organisation’s Information Risk Policy.
* **Risk Appetite:** Decides the organisation's response to identified risks.
* **Assurance:** Signs off the annual DSPT submission.

### Caldicott Guardian - {{ cto_name }}

* **Ethics:** Ensures patient-identifiable data is processed according to the 8 Caldicott Principles.
* **Advocacy:** Acts as the "conscience" of the organisation regarding patient confidentiality.

### Data Protection Officer (DPO) - {{ cto_name }}

* **Compliance:** Monitors adherence to UK GDPR and the Data Protection Act 2018.
* **Point of Contact:** Liaison for the ICO and data subjects (SARs/Objections).

### Cyber Security Lead (CTO) - {{ siro_name }}

* **Implementation:** Manages technical controls (MFA, Encryption, Vault, Civo).
* **Incident Response:** Leads technical containment during a security event.

## 2. Shared Responsibilities

* **Data Quality:** Both founders ensure that system inputs and processing logic maintain data integrity.
* **Training:** Both founders must maintain 100% completion of mandatory NHS Data Security training.
* **Spot Checks:** The SIRO and Cyber Lead jointly conduct bi-annual compliance spot checks.

## 3. Appraisal Workflow Roles

These roles apply to GMC-style 360 appraisal surveys run by a designated body, such as a hospital appraisal department. The designated body is responsible for how its appraisals are run; {{ platform_name }} provides the tools.

### Responsible Officer (RO) - Organisation Owner / Admin

* **Oversight:** Holds portfolio oversight of every appraisal in the organisation.
* **Two-Party Control:** Co-signs exception reviews before any rater linkage is disclosed. Cannot co-sign a request they raised.
* **Continuity:** Recovers an appraiser's surveys through the organisation key and re-wraps them to an incoming appraiser when an appraiser leaves. No data is orphaned.

### Appraiser - Survey Owner

* **Ownership:** Owns each appraisee's appraisal survey and is accountable for how its responses are handled.
* **Results:** Unlocks results through the organisation key and releases reports to the appraisee.
* **Nominations:** Approves colleague raters and issues their tokens for the cycle.
* **Exceptions:** Raises an exception review, with a reason, where a response indicates serious risk (patient safety or fitness to practise).

### Appraisee - Distributor and Self-Assessor

* **Distribution:** Generates token batches and QR codes for patient and colleague feedback, and sees completion counts.
* **Self-Assessment:** Completes their own self-assessment using a single self token.
* **Results:** Receives released reports as released. Has no access to live results, responses, exception reviews, or survey settings, and cannot manage members.
