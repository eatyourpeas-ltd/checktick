---
title: "Clinical Safety Case Report (DCB0129)"
category: clinical-safety
priority: 1
---

# Clinical Safety Case Report

**System:** {{ platform_name }} — Healthcare Survey Platform
**Standard:** DCB0129 (Clinical Risk Management: its Application in the Manufacture of Health IT Systems)
**Document Reference:** CSC-001
**Version:** 1.0
**Date:** April 2026
**Clinical Safety Officer (CSO):** {{ cso_name }}
**SIRO / Caldicott Guardian:** {{ siro_name }}
**Review Cycle:** Annual, or following any major system change

---

## 1. Purpose and Scope

This Clinical Safety Case Report provides a structured, evidence-based argument that {{ platform_name }} is acceptably safe for its intended clinical purpose. It has been prepared in accordance with NHS England's **DCB0129** standard.

This report covers:

- The {{ platform_name }} SaaS platform hosted at `checktick.uk`
- The self-hosted distribution made available via the open-source Docker image

It does **not** cover deployments where third parties have materially modified the codebase beyond the standard configuration options. Such deployments would require their own DCB0160-compliant Clinical Risk Management File from the deploying organisation.

---

## 2. System Description

{{ platform_name }} is an open-source healthcare survey platform designed for medical audit, research, and the collection of Patient-Reported Outcome Measures (PROMs). It is a web-based application built on Django (Python), containerised with Docker, and hosted on Northflank infrastructure in the UK.

### 2.1 Key Functional Domains

| Domain | Description |
| :--- | :--- |
| **Survey Creation** | Clinicians and researchers create structured surveys from a qusetion builder of question types, including Likert scales, free text, date pickers, dropdown lists, and repeat blocks. Surveys can also be created from text using a markdown notation developed for the purpose |
| **Branching & Logic** | Conditional question display and repeat/collection blocks allow complex clinical pathways to be modelled. |
| **AI Survey Generator** | An LLM-assisted interface allows users to describe survey requirements in natural language; the LLM produces markdown that is reviewed and validated before import. |
| **Survey Translation** | Surveys may be automatically translated into supported languages via an LLM pipeline; translations are validated before publication. |
| **Standardised Datasets and Dropdowns** | Lists to populate dropdown choices are provided, validated by the NHS Data Dictionary and Royal College of Paediatrics and Child Health, SNOMED CT. |
| **Standardised Question Bank** | Common groups of questions for reuse are hosted and can be published by teams either globally or for scoped use. |
| **Patient Data Collection** | Patients or participants complete surveys via a web-based link. Responses are encrypted in transit (TLS 1.2+) and at rest (AES-256-GCM). |
| **Clinician Dashboard** | Authenticated clinicians review aggregated and individual responses. Role-based access control (RBAC) restricts visibility to authorised users. |
| **Data Export & API** | Survey data can be exported (CSV/JSON). |
| **Audit Logging** | All data access, export, and modification events are written to an immutable audit log. |

### 2.2 Technology Summary

- **Language / Framework:** Python 3 / Django
- **Database:** PostgreSQL (Northflank-managed, UK South region)
- **Encryption:** AES-256-GCM at rest; TLS 1.2+ in transit
- **Hosting:** Northflank PaaS (UK)
- **Key Management:** HashiCorp Vault (enterprise) / environment-level secrets (standard)
- **Source Control:** GitHub (public repository, GPG-signed commits)
- **Authentication:** Local accounts with 2FA; OIDC SSO (Google / Microsoft 365)

---

## 3. Intended Use

{{ platform_name }} is intended for use as a **data collection and survey management platform** to support clinical audit, research, and patient-reported outcome measurement within UK health and social care settings.

### 3.1 Intended Users

- **Survey Creators:** Clinicians, clinical researchers, quality improvement leads, and healthcare administrators who design and manage surveys.
- **Survey Respondents:** Patients, service users, carers, or clinical staff completing surveys.
- **Data Reviewers:** Clinicians or analysts who access aggregated or individual survey responses to inform clinical decisions, audit processes, or research analysis.

### 3.2 Clinical Context

{{ platform_name }} is positioned as a **data collection tool**. It does not:

- Provide clinical diagnoses or treatment recommendations.
- Automatically alert clinicians to clinically urgent findings or safety-critical thresholds (without explicit configuration by the deploying organisation).
- Replace or integrate directly with a prescribing or clinical decision support system.

Any clinical decision made on the basis of data collected via {{ platform_name }} remains the sole professional responsibility of the qualified clinician reviewing that data.

### 3.3 Contraindications and Limitations

{{ platform_name }} is **not** intended for:

- **Emergency data collection** where system unavailability would directly endanger life.
- **Automated clinical triage** where survey scores directly trigger care pathways without clinician review.
- **Direct diagnostic reporting** without clinical oversight.

---

## 4. Clinical Risk Management Process

{{ platform_name }} follows a clinical risk management process aligned with DCB0129. This process encompasses:

1. **Hazard Identification** — Using structured review sessions, informed by system architecture, user research, and analogous hazard logs.
2. **Risk Estimation** — Each hazard is assessed for initial risk (without controls) using a 3x3 likelihood/severity matrix.
3. **Risk Evaluation & Control** — Existing and additional controls are identified and applied.
4. **Residual Risk Assessment** — The residual risk (with controls in place) is assessed against the acceptability criteria.
5. **Clinical Safety Argument** — A structured argument that the system is acceptably safe based on the evidence gathered.

### 4.1 Risk Acceptability Criteria

| Risk Level | Definition | Action |
| :--- | :--- | :--- |
| **Intolerable** | Unacceptable under any circumstances | System change or feature removal required before release |
| **ALARP** | As Low As Reasonably Practicable — risk reduced to lowest feasible level | Ongoing monitoring and technical/process controls maintained |
| **Acceptable** | Risk sufficiently low that no further action is required | Monitor and document |

### 4.2 Severity and Likelihood Scales

**Severity**

| Level | Definition |
| :--- | :--- |
| **High** | Severe or irreversible patient harm; significant delay in appropriate treatment; major breach of patient confidentiality affecting many individuals |
| **Medium** | Moderate patient harm; temporary disruption to clinical workflow; identifiable but limited privacy breach |
| **Low** | Negligible patient impact; minor inconvenience; rapidly recoverable; no lasting harm |

**Likelihood**

| Level | Definition |
| :--- | :--- |
| **High** | Expected to occur in the majority of deployments or use sessions |
| **Medium** | May occur in some deployments; occasional occurrence under normal conditions |
| **Low** | Unlikely under normal operating conditions; requires multiple failures or extreme circumstances |

**Residual Risk Matrix**

|  | Low Severity | Medium Severity | High Severity |
| :--- | :--- | :--- | :--- |
| **High Likelihood** | ALARP | Intolerable | Intolerable |
| **Medium Likelihood** | Acceptable | ALARP | Intolerable |
| **Low Likelihood** | Acceptable | Acceptable | ALARP |

---

## 5. Hazard Log

The following hazards have been identified through structured review of the system architecture, data flows, AI features, and analogous clinical software risks. Each hazard is assessed with and without existing controls.

---

### HAZARD-CS01: Clinically Inappropriate AI-Generated Survey Questions

| Field | Detail |
| :--- | :--- |
| **Hazard** | The AI survey generator produces questions that are clinically misleading, distressing, or missing items critical to patient safety outcome measurement. |
| **Potential Cause** | Ambiguous user prompt; LLM hallucination; prompt injection via manipulated input. |
| **Clinical Consequence** | Survey respondents may be exposed to inappropriate questions; clinicians may act on an incomplete or misleading dataset. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Medium |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) LLM has zero tool access — cannot modify surveys directly. (2) All LLM output is rendered as markdown subject to the full validated import pipeline before any data is saved. (3) Survey creators review AI output before import. (4) Survey creators retain full edit rights after import. (5) AI security and prompt injection controls are documented in [AI Security & Safety](/docs/llm-security/). (6) System prompt transparency — published publicly for independent review. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Maintain LLM sandboxing controls. Monitor published system prompt for drift. Annual review of AI safety posture. |

---

### HAZARD-CS02: Survey Translation Introduces Clinical Inaccuracy

| Field | Detail |
| :--- | :--- |
| **Hazard** | An LLM-translated survey contains clinically inaccurate terminology or culturally inappropriate phrasing, causing respondents to misinterpret questions and answer incorrectly. |
| **Potential Cause** | LLM translation error; mistranslation of clinical terms; validated scales translated without fidelity to the validated instrument. |
| **Clinical Consequence** | Clinically valid scores (e.g., validated PROM scores) may be invalidated; clinical decisions based on translated data may be incorrect. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Medium |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) Translation output is reviewed and approved by the survey creator before publication. (2) Survey creators are explicitly guided to verify clinical translations against validated instrument guidelines. (3) Translation pipeline is documented in [Survey Translation](/docs/survey-translation/). (4) The platform does not certify the clinical validity of translations; this responsibility lies with the survey creator. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Add explicit in-platform guidance cautioning users that translated validated scales must be back-translated and verified by a qualified clinician. Review annually. |

---

### HAZARD-CS03: Loss or Corruption of Survey Response Data

| Field | Detail |
| :--- | :--- |
| **Hazard** | Patient survey responses are lost, corrupted, or rendered inaccessible, meaning a clinician makes a clinical decision on an incomplete dataset. |
| **Potential Cause** | Database failure; accidental deletion; encryption key loss; software defect during data processing. |
| **Clinical Consequence** | Incomplete clinical datasets; delayed audit cycles; potential clinical decision-making on partial data. |
| **Initial Severity** | High |
| **Initial Likelihood** | Low |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) Daily automated encrypted backups within UK geography (RPO 24 hours). (2) Annual disaster recovery drill with documented restoration test log ([Restoration Test Log](/compliance/restoration-test-log/)). (3) AES-256-GCM encryption with Vault-managed key escrow to prevent permanent data loss. (4) Audit log of all data modification events. (5) Response submission is transactional — partial writes are rolled back. (6) RTO < 4 hours as documented in [Business Continuity Plan](/compliance/business-continuity-plan/). |
| **Residual Severity** | Medium |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Maintain backup cadence and annual DR test. Ensure key escrow procedures remain current. |

---

### HAZARD-CS04: System Unavailability During Active Clinical Use

| Field | Detail |
| :--- | :--- |
| **Hazard** | {{ platform_name }} is unavailable at a time when a clinical team depends on it for data collection or review, creating a gap in clinical workflow. |
| **Potential Cause** | Northflank PaaS outage; deployment failure; network disruption; DDoS. |
| **Clinical Consequence** | Delayed patient survey completion; delay in clinicians accessing outcome data; potential for clinical decision delay. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Low |
| **Initial Risk** | Acceptable |
| **Existing Controls** | (1) Northflank high-availability PaaS with SLA for UK region. (2) Fallback paper-based survey procedure documented and communicated to Trust leads. (3) Clinician outage notification within 2 hours of a High severity incident. (4) Monitoring and alerting via Northflank infrastructure dashboards. (5) {{ platform_name }} is not used for emergency triage or real-time life-critical monitoring — per the intended use limitations at Section 3.3. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Maintain Business Continuity Plan. Ensure Trust leads are trained annually on paper fallback procedure. |

---

### HAZARD-CS05: Incorrect Conditional Branching Causes Clinically Important Questions to be Skipped

| Field | Detail |
| :--- | :--- |
| **Hazard** | A survey creator misconfigures conditional branching rules, causing clinically important questions to be hidden from a subset of respondents. |
| **Potential Cause** | User configuration error; misunderstanding of branching logic; complex nested conditions interacting unexpectedly. |
| **Clinical Consequence** | Missing data for a clinically significant subset of patients; systematic bias in PROM dataset; clinical decisions based on incomplete patient group data. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Medium |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) Branching logic is validated at survey publish time — invalid or circular conditions are rejected. (2) Live survey preview allows creators to test all logical pathways before publication. (3) Branching and repeat logic is documented in [Branching & Repeats](/docs/branching-and-repeats/). (4) Survey creators retain full edit rights after publication, enabling rapid correction. (5) Response data includes which questions were shown to each respondent, supporting retrospective data quality review. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Consider adding a formal "branching path test" checklist prompt at the point of survey publication. Review annually. |

---

### HAZARD-CS06: Unauthorised Access to Patient-Identifiable Survey Data

| Field | Detail |
| :--- | :--- |
| **Hazard** | An unauthorised party gains access to patient-identifiable fields within survey responses. |
| **Potential Cause** | Compromised credentials; misconfigured RBAC; API key leakage; insider threat. |
| **Clinical Consequence** | Breach of patient confidentiality; ICO notification obligation; potential harm to patient (stigma, discrimination); erosion of patient trust. |
| **Initial Severity** | High |
| **Initial Likelihood** | Low |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) AES-256-GCM field-level encryption — encrypted fields are unreadable without the user's derived key. (2) RBAC enforced at organisation, team, and survey level. (3) 2FA enforced for all admin accounts; OIDC SSO optionally enforced by organisations. (4) Immutable audit log captures all data access events. (5) Scoped API keys with principle of least privilege. (6) Penetration test completed (AD24502) — findings remediated per [Pentest Remediation Response](/compliance/pentest-remediation-response-AD24502/). (7) Cyber Essentials Plus certification maintained. (8) Annual vulnerability scanning and patch management. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Maintain annual penetration testing cycle. Monitor audit logs for anomalous access patterns. |

---

### HAZARD-CS07: Export or API Response Contains Incorrect or Incomplete Data

| Field | Detail |
| :--- | :--- |
| **Hazard** | A data export or API response delivered to a clinician or clinical system contains incorrect, truncated, or mis-attributed survey responses. |
| **Potential Cause** | Software defect in export pipeline; API filtering error; encoding issue; race condition during concurrent submissions. |
| **Clinical Consequence** | Clinician or integrated system acts on incorrect data, potentially leading to a flawed clinical audit conclusion or erroneous entry in an EPR. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Low |
| **Initial Risk** | Acceptable |
| **Existing Controls** | (1) Export pipeline is covered by automated regression tests. (2) Exports are stamped with survey version, export timestamp, and responding user identifier, supporting data provenance verification. (3) API responses include pagination metadata and response counts to detect truncation. (4) All exports are logged in the audit trail with the requesting user's identity and scope. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Ensure export regression test suite is maintained with each software release. |

---

### HAZARD-CS08: Platform Used Outside of Intended Clinical Scope

| Field | Detail |
| :--- | :--- |
| **Hazard** | {{ platform_name }} is deployed as a direct diagnostic or triage decision support tool rather than as a data collection instrument, beyond the stated intended use. |
| **Potential Cause** | Deploying organisation configures the platform without clinical risk management assessment (DCB0160); lack of awareness of intended use limitations. |
| **Clinical Consequence** | Clinical decisions made without appropriate clinician oversight; automated survey scores used as diagnoses; patient harm from unsupported clinical use. |
| **Initial Severity** | High |
| **Initial Likelihood** | Low |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) Intended use limitations are explicitly stated in public documentation and this Clinical Safety Case. (2) Terms of Service prohibit use in emergency or life-critical contexts without appropriate clinical governance. (3) {{ platform_name }} does not include automated clinical alert thresholds or prescribing integration by default. (4) Deploying healthcare organisations are directed to complete their own DCB0160 Clinical Risk Management File. (5) Self-hosting documentation includes a clinical governance section advising on deployment responsibilities. |
| **Residual Severity** | Medium |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Ensure DCB0160 guidance is included in self-hosting documentation and onboarding communications for NHS Trust customers. Consider a formal safe use notice during account setup. |

---

### HAZARD-CS09: Encryption Key Loss Renders Survey Data Permanently Inaccessible

| Field | Detail |
| :--- | :--- |
| **Hazard** | Encryption keys are lost without recoverable backup, rendering all patient survey data permanently inaccessible. |
| **Potential Cause** | Staff departure without key handover; Vault misconfiguration; loss of all unseal key shares simultaneously. |
| **Clinical Consequence** | Complete and permanent loss of clinical audit data; potential regulatory obligation to notify affected participants; reputational harm. |
| **Initial Severity** | High |
| **Initial Likelihood** | Low |
| **Initial Risk** | ALARP |
| **Existing Controls** | (1) Vault unseal key shares are distributed across multiple secure locations per documented procedures. (2) Break-glass credentials held by both SIRO and CTO independently. (3) Key escrow architecture designed to prevent permanent loss — documented in [Encryption Technical Reference](/docs/encryption-technical-reference/) and [Key Management for Administrators](/docs/key-management-for-administrators/). (4) Annual key recovery drill is included in the disaster recovery testing programme. (5) Succession plan documented in [Business Continuity Plan](/compliance/business-continuity-plan/) — SIRO holds emergency credentials if CTO unavailable. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Ensure key recovery drill is performed annually and results documented. Review key holder succession list at each annual DR test. |

---

### HAZARD-CS10: Failed or Delayed Clinician Notification of Survey Completion

| Field | Detail |
| :--- | :--- |
| **Hazard** | A notification to a clinician that a patient has completed a survey fails to send or is significantly delayed. |
| **Potential Cause** | Microsoft 365 transient failure; recipient email server blocking; configuration error in notification settings. |
| **Clinical Consequence** | Clinician unaware of completed survey; delay in reviewing PROM or audit response; potential delay in clinical follow-up. |
| **Initial Severity** | Medium |
| **Initial Likelihood** | Low |
| **Initial Risk** | Acceptable |
| **Existing Controls** | (1) Clinicians can access and query all completed responses via the authenticated dashboard at any time, independent of notifications. (2) Microsoft 365 delivery receipts are logged. (3) Notification configuration is tested as part of deployment validation. (4) Audit log captures survey completion events with timestamps. |
| **Residual Severity** | Low |
| **Residual Likelihood** | Low |
| **Residual Risk** | Acceptable |
| **Action** | Provide guidance in documentation that clinicians should not rely solely on email notification for time-critical follow-up. Consider in-platform notification queue as future enhancement. |

---

## 6. Hazard Log Summary

| ID | Hazard Summary | Initial Risk | Residual Risk |
| :--- | :--- | :--- | :--- |
| CS01 | AI-generated clinically inappropriate questions | ALARP | Acceptable |
| CS02 | AI translation introduces clinical inaccuracy | ALARP | Acceptable |
| CS03 | Loss or corruption of survey response data | ALARP | Acceptable |
| CS04 | System unavailability during clinical use | Acceptable | Acceptable |
| CS05 | Branching misconfiguration causes skipped questions | ALARP | Acceptable |
| CS06 | Unauthorised access to patient data | ALARP | Acceptable |
| CS07 | Export / API returns incorrect data | Acceptable | Acceptable |
| CS08 | Use outside intended clinical scope | ALARP | Acceptable |
| CS09 | Encryption key loss | ALARP | Acceptable |
| CS10 | Failed clinician notification | Acceptable | Acceptable |

All identified hazards have a **residual risk of Acceptable** following application of existing controls.

---

## 7. Safety Argument

The safety argument for {{ platform_name }} rests on the following evidence:

### 7.1 Strong Technical Controls

- Comprehensive encryption (AES-256-GCM at rest, TLS 1.2+ in transit) protects data confidentiality.
- RBAC, 2FA, and scoped API keys prevent unauthorised access.
- Immutable audit logging provides traceability for all data access.
- Automated backup and tested recovery procedures protect against data loss.
- AI features are sandboxed with zero tool access, with all output validated before use.

### 7.2 Governance Maturity

- DSPT compliance is maintained with board approval and annual review.
- Cyber Essentials Plus certification independently verified.
- Penetration testing completed with all findings remediated.
- Caldicott Guardian oversight is documented.
- Staff training and annual competency assessment in place per the [Training & Awareness Log](/compliance/training/).

### 7.3 Intended Use Clarity

- {{ platform_name }} is explicitly a data collection platform, not a clinical decision support or diagnostic tool.
- Terms of Service and documentation clearly state the intended use and its limitations.
- Deploying organisations are directed to their own DCB0160 obligations.

### 7.4 Residual Risk Position

All ten identified hazards have been reduced to the **Acceptable** level following application of existing technical and process controls. No hazards remain at ALARP or Intolerable level. There are no outstanding safety actions with a blocking status.

---

## 8. Conclusion and Residual Risk Statement

On the basis of the hazard identification and risk assessment set out in this Clinical Safety Case Report, {{ platform_name }} is considered **acceptably safe** for its intended use as a healthcare survey and PROM data collection platform within UK health and social care settings, when operated in accordance with the guidance provided in the system documentation.

**Residual risks** exist as acknowledged above (Sections 5.1 to 5.10). These residual risks are accepted on the grounds that:

1. All controls are technical, procedural, or both, and are currently in operation.
2. No hazard poses a risk that could not be detected and remediated prior to patient harm.
3. {{ platform_name }} does not provide direct clinical diagnoses or autonomous clinical decision support, meaning a qualified clinician reviews all data before any clinical decision is taken.
4. The software is not deployed in emergency or life-critical monitoring contexts.

This Clinical Safety Case will be reviewed:

- **Annually** as part of the DSPT annual review cycle.
- **Following any major software release** that changes the clinical data pipeline, AI features, export mechanisms, or authentication architecture.
- **Following any patient safety incident** linked to use of the platform.

---

## 9. Actions and Recommendations Summary

| Ref | Action | Owner | Target Date |
| :--- | :--- | :--- | :--- |
| ACT-CS01 | Maintain LLM sandboxing controls; annual review of AI safety posture | {{ cto_name }} | Annual (April) |
| ACT-CS02 | Add in-platform guidance that translated validated scales require clinician back-translation verification | {{ cto_name }} | Next release |
| ACT-CS03 | Maintain backup cadence and annual DR test with documented results | {{ cto_name }} | Annual (April) |
| ACT-CS04 | Annual briefing to Trust leads on paper fallback procedure | {{ siro_name }} | Annual (April) |
| ACT-CS05 | Consider adding branching path test checklist prompt at survey publication | {{ cto_name }} | Next release |
| ACT-CS06 | Maintain annual penetration testing; monitor audit logs for anomalous access | {{ cto_name }} | Annual (October) |
| ACT-CS07 | Maintain export regression test suite with each software release | {{ cto_name }} | Each release |
| ACT-CS08 | Ensure DCB0160 guidance is included in self-hosting documentation and NHS Trust onboarding | {{ siro_name }} | Next release |
| ACT-CS09 | Annual key recovery drill; review key holder succession at annual DR test | {{ cto_name }} | Annual (April) |
| ACT-CS10 | Add documentation guidance that clinicians should not rely solely on email notification for time-critical follow-up | {{ cto_name }} | Next release |

---

## 10. Sign-off and Approval

This Clinical Safety Case Report has been reviewed and approved by the Clinical Safety Officer for {{ platform_name }} and is considered current as at the date below.

| Role | Name | Date | Signature |
| :--- | :--- | :--- | :--- |
| **Clinical Safety Officer (CSO)** | {{ cso_name }} | April 2026 | *(signed copy held securely)* |
| **SIRO / Caldicott Guardian** | {{ siro_name }} | April 2026 | *(signed copy held securely)* |
| **CTO** | {{ cto_name }} | April 2026 | *(signed copy held securely)* |

---

## Appendix A: Related Documentation

| Document | Reference | Location |
| :--- | :--- | :--- |
| Security Overview | OWASP compliance | [/docs/security-overview/](/docs/security-overview/) |
| Authentication & Permissions | Access control | [/docs/authentication-and-permissions/](/docs/authentication-and-permissions/) |
| Encryption Technical Reference | Encryption architecture | [/docs/encryption-technical-reference/](/docs/encryption-technical-reference/) |
| AI Security & Safety | LLM security | [/docs/llm-security/](/docs/llm-security/) |
| Business Continuity Plan | DR / BCP | [/compliance/business-continuity-plan/](/compliance/business-continuity-plan/) |
| Caldicott Guardian Statement | Patient data governance | [/compliance/caldicott-statement/](/compliance/caldicott-statement/) |
| DPIA: Survey Platform | Data protection | [/compliance/dpia-survey-platform/](/compliance/dpia-survey-platform/) |
| Risk Register | Operational risk | [/compliance/risk-register/](/compliance/risk-register/) |
| Incident Response Plan | Security incidents | [/compliance/incident-response-plan/](/compliance/incident-response-plan/) |
| Branching & Repeats | Survey logic | [/docs/branching-and-repeats/](/docs/branching-and-repeats/) |
| Survey Translation | Translation pipeline | [/docs/survey-translation/](/docs/survey-translation/) |
| Restoration Test Log | DR evidence | [/compliance/restoration-test-log/](/compliance/restoration-test-log/) |
| Pentest Response AD24502 | Penetration testing | [/compliance/pentest-remediation-response-AD24502/](/compliance/pentest-remediation-response-AD24502/) |

---

## Appendix B: Glossary

| Term | Definition |
| :--- | :--- |
| **CSO** | Clinical Safety Officer — the individual accountable for clinical risk management under DCB0129. Must have appropriate clinical and health IT safety training. |
| **DCB0129** | NHS England standard for clinical risk management in the manufacture of health IT systems. |
| **DCB0160** | NHS England standard for clinical risk management in the deployment of health IT systems. Applies to organisations deploying {{ platform_name }}. |
| **PROM** | Patient-Reported Outcome Measure — a validated questionnaire completed by patients to measure health outcomes. |
| **ALARP** | As Low As Reasonably Practicable — a risk level where all feasible controls have been applied but some residual risk remains. |
| **RBAC** | Role-Based Access Control — restricts system access based on the user's role within an organisation. |
| **Vault** | HashiCorp Vault — the key management system used to secure and manage encryption keys. |
| **EPR** | Electronic Patient Record — a clinical information system used to store and manage patient health records. |
| **DSPT** | Data Security and Protection Toolkit — the NHS self-assessment framework for information governance compliance. |
| **SIRO** | Senior Information Risk Owner — the board-level individual accountable for information risk. |
