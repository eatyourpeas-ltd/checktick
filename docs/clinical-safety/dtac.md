---
title: "Digital Technology Assessment Criteria (DTAC v2.0)"
category: clinical-safety
priority: 2
---

# Digital Technology Assessment Criteria (DTAC v2.0)

**Product:** {{ platform_name }}
**Manufacturer:** Eatyourpeas Ltd
**DTAC Version:** 2.0 (24 February 2026)
**Submission Date:** April 2026
**Document Reference:** DTAC-001

> **Note for assessors:** Manufacturers must provide this form in lieu of v1.0 from 6 April 2026. This completed form should be read alongside the supporting documentation listed in the checklist at the end of this document.

---

## A. Company Information (Non-assessed)

| Code | Question | Response |
| :--- | :--- | :--- |
| A1 | Name of company | Eatyourpeas Ltd |
| A2 | Name of product | {{ platform_name }} |
| A3 | Version number | {{ platform_version }} |
| A4 | Type of product | SaaS (Software as a Service) |
| A5 | Name and job title of key contact | {{ cso_name }}, Clinical Safety Officer / Director |
| A6 | Key contact email address | {{ cso_email }} |
| A7 | Key contact phone number | **apply to dpo@checktick.uk** |
| A8 | Registered address | {{ company_address }} |
| A9 | Country of registration | England |
| A10 | Companies House registration number | {{ company_registration_number }} |
| A11 | Date of last CQC assessment | Not applicable — {{ platform_name }} is a software platform and does not require CQC registration |
| A12 | Latest CQC report | Not applicable |

---

## B. Value Proposition (Non-assessed)

| Code | Question | Response |
| :--- | :--- | :--- |
| B1 | Intended use of the product | Clinical Support; Workforce efficiency; Administration of care delivery |
| B2 | Description of what the product does and how it is used | {{ platform_name }} is an open-source, web-based healthcare survey platform for medical audit, research, and Patient-Reported Outcome Measure (PROM) collection. Clinicians and researchers create structured surveys using a validated question builder (Likert scales, free text, date pickers, dropdown lists, branching logic, and repeat blocks). Surveys can also be created from text using a purpose-built markdown notation, or via an AI-assisted generator. Surveys are distributed to patients or participants via a secure web link. Survey responses are encrypted end-to-end and accessible only to authorised clinical users via a role-based access control dashboard. Data can be exported (CSV/JSON) or accessed via a scoped REST API. The platform supports validated standardised datasets derived from the NHS Data Dictionary, SNOMED CT, and the Royal College of Paediatrics and Child Health. It is available as a managed SaaS service at checktick.uk and as a self-hosted open-source deployment. |
| B3 | Intended users, proven benefits, and validation | **Intended users:** Clinicians, clinical researchers, quality improvement leads, healthcare administrators (survey creators); patients and service users (survey respondents); clinical analysts and auditors (data reviewers). **Benefits:** Replaces paper-based or spreadsheet-driven clinical audit and PROM collection with a secure, encrypted, auditable digital workflow, reducing transcription errors and improving data quality. Supports i18n with survey translation for diverse patient populations. **Validation:** > **TODO:** Document any formal evaluations, pilot deployments, or user research studies completed. Include Trust or service names if permission has been given. |
| B4 | Data flow between product and Health IT System | Data flows are documented in the [Data Flow Mapping](/compliance/data-flow-mapping/) document. Summary: patient responses flow from browser → TLS 1.2+ → Django application → AES-256-GCM encrypted PostgreSQL (Northflank UK-South). Clinician access and data export are via authenticated HTTPS sessions. API integration with EPR or clinical dashboards is supported via scoped REST API keys over HTTPS. No data leaves the UK. > **TODO:** Attach or link to a user journey map / data flow diagram suitable for assessors. |

---

## C. Technical Questions (Assessed Sections)

### C1 — Clinical Safety

| Code | Question | Response |
| :--- | :--- | :--- |
| C1.1.1 | Does your product qualify as Software or AI as a Medical Device? | **No.** {{ platform_name }} is a data collection and survey management platform. It does not provide clinical diagnoses, interpret clinical data to drive treatment decisions, or perform any function that would qualify it as a Medical Device under the MHRA MDR 2002 or the MHRA's Software and AI as a Medical Device guidance. The AI Survey Generator assists with survey *creation* (not patient assessment) and its output is validated by a clinician before use. |
| C1.1.2 | Is your product classified as a standalone medical device? | **No.** As above — the platform does not meet the definition of a medical device. |
| C1.2 | Is the product designed to influence or support real-time direct care? | **No.** {{ platform_name }} is a data collection instrument. All clinical decisions made on the basis of data collected via the platform remain the exclusive professional responsibility of the qualified clinician reviewing that data. The platform does not generate clinical alerts, recommendations, or automated care pathway triggers based on survey scores. |
| C1.2.1 | Justification if product does not fall in scope of DCB0129 | Not applicable — {{ platform_name }} has voluntarily applied DCB0129 as best practice, as documented below. |
| C1.2.2 | Have you undertaken Clinical Risk Management (DCB0129)? | **Yes.** {{ platform_name }} has undertaken a full Clinical Risk Management process in accordance with DCB0129, including hazard identification, risk estimation, and residual risk assessment. |
| C1.2.3 | Detail your clinical risk management system | A clinical risk management system has been in place throughout the development and operation of {{ platform_name }}. This includes: a documented Clinical Safety Case Report (CSC-001); a structured Hazard Log covering 10 identified hazards; ongoing review of clinical risks at the annual DSPT review cycle and following major releases; designated Clinical Safety Officer (CSO); board-level sign-off by the SIRO and CTO. See [Clinical Safety Case Report (DCB0129)](/clinical-safety/clinical-safety-case/) for full detail. |
| C1.2.4 | Clinical Safety Case Report and Hazard Log | **Provided.** See [Clinical Safety Case Report — Document Reference CSC-001](/clinical-safety/clinical-safety-case/). The Hazard Log is embedded within the Clinical Safety Case Report (Section 5) and covers 10 hazards with initial and residual risk assessments. All residual risks are rated Acceptable. |
| C1.2.5 | Name, profession, and registration of Clinical Safety Officer | **Name:** {{ cso_name }} **Profession:** Medical Doctor (MB BS / equivalent) **Registration:** {{ cso_gmc_number }} for {{ cso_name }}. Also confirm completion of NHS England Health IT Clinical Safety Training (eLearning for Healthcare or equivalent). |

---

### C2 — Data Protection

| Code | Question | Response |
| :--- | :--- | :--- |
| C2.1 | Compliant with annual DSPT assessment? | **Confirmed.** {{ platform_name }} (Eatyourpeas Ltd) completed the annual NHS Data Security and Protection Toolkit assessment on 6 April 2026. ODS code: {{ company_ods_code }}. Update this entry with the published submission status once ratified by NHSE. |
| C2.2 | Does the product process personal data (including data of deceased individuals)? | **Yes.** The platform processes health-related survey data which may include patient-identifiable information such as name, date of birth, NHS number, and clinical responses. |
| C2.2.1 | Evidence of ICO registration | **Provided.** Eatyourpeas Ltd is registered with the Information Commissioner's Office as a data controller. ICO Registration: {{ ico_number }} [certificate](https://ico.org.uk/ESDWebPages/Entry/{{ ico_number }}) |
| C2.2.2 | Data Protection Impact Assessment (DPIA) | **Provided.** A DPIA has been completed for the {{ platform_name }} survey platform. See [DPIA: Survey Platform](/compliance/dpia-survey-platform/). |
| C2.2.3 | Transparency information / Privacy Notice | **Provided.** The Privacy Notice is publicly available at [https://checktick.uk/docs/privacy-notice/](/docs/privacy-notice/). It is linked from the platform footer, the sign-up flow, and all published survey landing pages. |
| C2.2.4 | Product terms and conditions / EULA | **Provided.** Terms of Service are publicly available at [https://checktick.uk/docs/terms-of-service/](/docs/terms-of-service/). These set out the lawful basis for processing, data subject rights, and the responsibilities of survey creators (data controllers) in relation to their participants. |
| C2.2.5 | Location of data storage and processing | **UK only.** All patient and survey data is stored on Northflank-managed PostgreSQL infrastructure in the UK-South region. No patient-identifiable data is transferred outside the United Kingdom for any purpose, including support, maintenance, or AI processing. |
| C2.2.6 | If outside UK, compliance arrangements | Not applicable — all data remains within the UK. |

---

### C3 — Technical Security

| Code | Question | Response |
| :--- | :--- | :--- |
| C3.1 | Cyber Essentials Certificate | **Provided.** {{ platform_name }} holds a current **Cyber Essentials Plus** certificate. See [Cyber Essentials Plus Certificate](/compliance/files/cyber-essentials-plus/). |
| C3.2 | Signed the NHS Cyber Security Charter for Suppliers | > **TODO:** Confirm whether Eatyourpeas Ltd has signed the NHS Cyber Security Charter for NHS Suppliers. If yes, C3.3–C3.6 may be skippable. If not yet signed, complete C3.3–C3.6 below (all are met). |
| C3.3 | Summary report of external penetration test (last 12 months) | **Provided.** An external web application penetration test was conducted 16–19 March 2026 by an independent CREST-accredited assessor (reference AD24502). The Letter of Attestation confirming no vulnerabilities scoring 7.0+ (CVSS) is available at [Pentest Attestation AD24502-RPT-01](/compliance/files/pentest-AD24502-RPT-01/). All findings have been fully remediated — see [Pentest Remediation Response](/compliance/pentest-remediation-response-AD24502/). |
| C3.4 | Adherence to DSIT/NCSC Software Security Code of Practice | **Confirmed.** {{ platform_name }}'s Secure Software Development Lifecycle (SSDLC) policy is aligned to the DSIT/NCSC Software Security Code of Practice. Controls include: mandatory GPG-signed commits; branch protection rules; automated dependency scanning (`pip-audit`); Subresource Integrity (SRI) verification for all third-party JavaScript; automated security testing in CI/CD; and a documented vulnerability management and patching policy. See [SSDLC Policy](/compliance/ssdlc-policy/) and [Security Overview](/docs/security-overview/). |
| C3.5 | Plan for implementing Multi-Factor Authentication (MFA) | **Yes.** MFA is implemented and enforced. All administrative and staff access requires MFA via OIDC SSO (Google / Microsoft 365). Platform users are encouraged to enable 2FA; organisation administrators may enforce 2FA for all members. |
| C3.5.1 | MFA enabled for supplier privileged access? | **Yes.** All privileged access to Northflank (hosting), GitHub (source code), and the platform admin console requires MFA. No privileged access is possible without MFA authentication. |
| C3.6 | Logging and reporting requirements defined | **Yes.** Comprehensive audit logging is implemented across all layers: (1) an immutable application-level audit log captures all data access, export, modification, and authentication events with timestamps and user identity; (2) infrastructure-level logging via Northflank; (3) network-level logging via DNS and ingress. Logging policy and retention are documented in [Logging Policy](/compliance/logging-policy/). |

---

### C4 — Interoperability

| Code | Question | Response |
| :--- | :--- | :--- |
| C4.1 | Does the product expose any APIs? | **Yes.** {{ platform_name }} exposes a RESTful API for programmatic access to survey data. |
| C4.1.1 | Do APIs use international/industry standards? | **Yes.** The API is built on **RESTful HTTP** principles and documented using **OpenAPI 3.0** (accessible at `/api/schema` and via the ReDoc interface at `/api/redoc`). Authentication uses **API key** tokens (via `Authorization: Api-Key` header) conforming to industry standard patterns. Data is returned as **JSON**. |
| C4.1.2 | Do APIs follow GDS Open API Best Practice? | **Confirmed.** The API follows GDS API technical and data standards: versioned endpoints, consistent JSON responses, standard HTTP status codes, and a published OpenAPI schema. See [API Reference](/docs/api/). |
| C4.1.3 | Basis on which APIs are made available to third parties | API access is scoped per survey and per organisation, operating on the principle of least privilege. API keys are generated by authenticated users through the MFA-protected web UI and can be revoked at any time. Each key can only access data within the survey(s) explicitly scoped to it. Revoking a user's account immediately revokes all associated keys. Rate limiting is enforced at the Northflank ingress layer. All API access is logged in the immutable audit trail. |
| C4.2 | Intended to share or receive data from national or local systems? | **Not currently by default.** The platform provides an API that deploying organisations may use to integrate with local EPR or clinical dashboard systems. Out-of-the-box, {{ platform_name }} does not have pre-built integrations with national systems (PDS, NHS login, DAPB3051). |
| C4.2.1 | Capable of using NHS number to identify patient data? | **Yes.** {{ platform_name }} provides a validated NHS number question type with real-time check-digit validation conforming to the NHS number algorithm. Survey creators may include this as a patient identifier field. The platform stores and exports NHS numbers in their validated format. |
| C4.2.2 | Integrate with NHS PDS or local record systems? | **No** — not by default. The platform API allows local integrations to be built by deploying organisations. Native PDS lookup integration is not currently implemented. > **TODO:** If PDS integration is planned, document the timeline here. |
| C4.2.3 | Approach to identify records if no PDS integration | Record linkage relies on identifiers collected within surveys as configured by the survey creator. These may include NHS number (with check-digit validation), MRN/local hospital number, name, and date of birth, as determined by the clinical team deploying the survey. Survey creators are responsible for the identifier strategy appropriate to their clinical context, per their own DCB0160 Clinical Risk Management File. |
| C4.2.4 | Use NHS login to verify identity (if patient-facing)? | **No.** Patient-facing surveys are accessed via a unique secure link. Authentication for clinician and staff accounts uses OIDC SSO (Google / Microsoft 365) or local accounts with 2FA. > **TODO:** If NHS login integration is planned, document the timeline and approach here. |
| C4.2.5 | Support DAPB3051 for public health / social care? | **Not applicable** to the current version. |
| C4.2.6 | Approach to authenticating users (not using NHS login) | Clinician and staff accounts are authenticated via: (1) local username/password with enforced 2FA; or (2) OIDC SSO via Google Workspace or Microsoft 365, with MFA enforced at the identity provider level. Session management follows OWASP best practice (short-lived JWT tokens; secure, HttpOnly cookies; CSRF protection). See [Authentication & Permissions](/docs/authentication-and-permissions/). |

---

## D. Key Principles for Success

### D1 — Usability and Accessibility

| Code | Question | Response |
| :--- | :--- | :--- |
| D1.1 | How the product fits into existing care pathways | {{ platform_name }} is designed to slot into existing clinical workflows as a standalone data collection layer. Survey creators define the clinical pathway context; the platform provides the digital collection mechanism. Typical use cases include: pre-appointment PROM collection distributed by link or QR code; post-encounter audit questionnaires; longitudinal outcome measurement at defined timepoints. The platform supports conditional branching and repeat structures to mirror complex clinical pathways. > **TODO:** Attach user journey documentation or a care pathway integration guide for the specific deployments being assessed. |
| D1.2 | Testing with intended users to validate usability | > **TODO:** Document any formal usability testing, user research sessions, or pilot deployments completed with clinicians and/or patients. Include participant numbers, methods, and any changes made as a result. |
| D1.3 | Considered the Accessible Information Standard | **Confirmed.** {{ platform_name }} is built with accessibility as a core principle. The platform supports survey translation into multiple languages; all UI components follow semantic HTML and ARIA standards. Survey creators are guided to consider accessible information needs when designing surveys. See [Accessibility](/docs/accessibility/). |
| D1.4 | Is the product a web or mobile application? | **Yes** — {{ platform_name }} is a web application, accessible on any modern browser on desktop, tablet, and mobile. No native app installation is required. |
| D1.4.1 | Comply with WCAG 2.2 AA or higher? | **Yes** — the platform targets **WCAG 2.1 AA** compliance (with WCAG 2.2 AA improvements in progress). Automated accessibility testing using `axe-core` is integrated into the test suite and runs against all key page templates. See [Accessibility](/docs/accessibility/). |
| D1.4.2 | Timescale to obtain WCAG 2.2 AA | > **TODO:** Confirm target date for full WCAG 2.2 AA compliance. Current status: WCAG 2.1 AA met; known WCAG 2.2 items under active development. |
| D1.4.3 | Link to published accessibility statement | [https://checktick.uk/docs/accessibility/](/docs/accessibility/) |
| D1.5 | Average service availability (past 12 months) | > **TODO:** Insert service availability percentage to two decimal places (e.g. 99.95%) from Northflank uptime monitoring for the 12 months preceding this submission. |

---

## Supporting Documentation Checklist

| Item | Document | Status |
| :--- | :--- | :--- |
| A11 | CQC Report | Not applicable |
| B4 | User journey maps and data flow diagrams | > **TODO:** Prepare and attach |
| C1.1 | Pre-Acquisition Questionnaire (PAQ) — Medical Device | Not applicable (not a medical device) |
| C1.2.3 | Clinical Safety Case Report | ✅ [CSC-001 — Clinical Safety Case Report (DCB0129)](/clinical-safety/clinical-safety-case/) |
| C1.2.4 | Hazard Log | ✅ Embedded in [Clinical Safety Case Report](/clinical-safety/clinical-safety-case/) Section 5 |
| C2.2.1 | ICO registration certificate | > **TODO:** Attach current ICO certificate (ZB-XXXXXXX) |
| C2.2.2 | Data Protection Impact Assessment | ✅ [DPIA: Survey Platform](/compliance/dpia-survey-platform/) |
| C2.2.4 | Terms and Conditions / EULA | ✅ [Terms of Service](/docs/terms-of-service/) |
| C3.1 | Cyber Essentials Plus Certificate | ✅ [Certificate (PDF)](/compliance/files/cyber-essentials-plus/) |
| C3.3 | External Penetration Test Summary Report | ✅ [Attestation AD24502-RPT-01 (PDF)](/compliance/files/pentest-AD24502-RPT-01/) |
| D1.1 | User journeys / care pathway integration | > **TODO:** Prepare and attach |

---

## Outstanding Items Summary

The following items require action before this form is submitted to a procuring health or care organisation:

| Ref | Item | Owner |
| :--- | :--- | :--- |
| B3 | Document formal evaluations, pilot deployments, or user research | {{ siro_name }} |
| B4 | Prepare user journey map / data flow diagram | {{ cto_name }} |
| C2.1 | Update with ratified DSPT submission status once published by NHSE | {{ siro_name }} |
| C2.2.1 | Insert ICO registration number; attach certificate | {{ siro_name }} |
| C3.2 | Confirm whether NHS Cyber Security Charter has been or should be signed | {{ cto_name }} |
| C4.2.2 | Document PDS integration plan/timeline if applicable | {{ cto_name }} |
| C4.2.4 | Document NHS login integration plan/timeline if applicable | {{ cto_name }} |
| D1.1 | Prepare care pathway / user journey documentation | {{ siro_name }} |
| D1.2 | Document usability testing with intended users | {{ siro_name }} |
| D1.4.2 | Confirm target date for full WCAG 2.2 AA compliance | {{ cto_name }} |
| D1.5 | Insert 12-month service availability percentage from Northflank monitoring | {{ cto_name }} |

---

**Prepared by:** {{ cso_name }}, Clinical Safety Officer
**Date:** April 2026
**Version:** Draft 1.0 — pending completion of outstanding items above

---

## Blank Form on which the above has been based

## Introduction

This form is **version 2.0** and was last updated on **24 February 2026**. Manufacturers must provide this form in lieu of the older v1.0 form from **6 April 2026** when requested by health and care organisations to facilitate assurance of Digital Health Technology products. Prior to this date, care providers should accept whichever version (1.0 or 2.0) is provided by the manufacturer.

The DTAC is the assessment framework for digital health technologies (DHTs) bringing together baseline standards and policies. DHTs must be assessed against these standards to be considered safe for use in the Health and Social care system in England.

### Scope of DTAC

Digital Health Technologies include software—mobile or web applications or SaaS—designed to improve health outcomes or system functions.

| In-scope of DTAC | Out of scope of DTAC |
| :--- | :--- |
| DHTs to improve health outcomes  | Hardware, onboard software, embedded software in hardware devices  |
| DHTs to improve how the health and care system functions  | DTAC is not intended for onboard software (e.g. firmware) or IVD medical devices (e.g. laboratory equipment)  |
| Medical devices classed as software or AI as a medical device  | Products not marketed specifically for a health or care context (e.g. HR or payroll systems)  |
| Software designed to help people manage their own health or well-being  | |
| Software designed to help deliver, manage, or administrate the provision of care  | |
| Software designed to release staff time or improve efficiency  | |

### Form Components

1.  **Section A & B:** Company information and Value proposition (Non-assessed context).
2.  **Section C1-C4:** Core assessment criteria (Assessed sections - Must meet these to pass).
3.  **Section D:** Usability and Accessibility principles (Scored element).

---

## A. Company Information (Non-assessed)

| Code | Question | Options |
| :--- | :--- | :--- |
| A1 | Provide the name of your company. | Free text  |
| A2 | Provide the name of your product. | Free text  |
| A3 | Provide the version number of your product this form corresponds to | Free text  |
| A4 | State the type of product. | Standalone Software / Mobile App / Wearable / SaaS / Other  |
| A5 | Name and job title of the key contact. | Free text  |
| A6 | Key contact's email address. | Free text  |
| A7 | Key contact's phone number. | Free text  |
| A8 | Registered address of your company. | Free text  |
| A9 | In which country is your organisation registered? | Free text  |
| A10 | Companies House registration / Charity number. | Free text  |
| A11 | Date of last CQC assessment (if required). | Date | Not applicable  |
| A12 | Provide latest CQC report (if applicable). | Provided | Not applicable  |

---

## B. Value Proposition (Non-assessed)

| Code | Question | Options | Supporting Information |
| :--- | :--- | :--- | :--- |
| B1 | What is the intended use of the product? | Patient Care / Diagnostics / Clinical Support / Workforce / Other  | |
| B2 | Description of what the product does and how it is used. | Free text  | High-level summary required. |
| B3 | Intended users, proven benefits, and validation. | Free text  | Include evaluation or clinical trial info. |
| B4 | Information about data flow between product and Health IT System. | Provided | Not available  | Provide user journey maps/data flows. |

---

## C. Technical Questions (Assessed Sections)

### C1 - Clinical Safety

Establishing that the product is clinically safe. DCB0129 applies to manufacturers of Health IT systems.

| Code | Question | Options | Scoring Criteria (To Pass) |
| :--- | :--- | :--- | :--- |
| C1.1.1 | Does your product qualify as Software or AI as a Medical Device? | Yes \| No  | If Yes, provide a completed PAQ form. |
| C1.1.2 | Is your product classified as a standalone medical device? | Yes \| No  | Determines if DCB0129 applies if not a standalone device. |
| C1.2 | Is product designed to influence/support real-time direct care? | Yes \| No  | Determines scope of DCB0129. |
| C1.2.1 | Justification if product does not fall in scope of DCB0129. | Free Text  | Must provide reasons if claiming out of scope. |
| C1.2.2 | Have you undertaken Clinical Risk Management (DCB0129)? | Yes \| No  | Must confirm compliance with DCB0129. |
| C1.2.3 | Detail your clinical risk management system. | Provided \| Not provided  | Demonstrate a system was in place throughout development. |
| C1.2.4 | Supply Clinical Safety Case Report and Hazard Log. | Provided \| Not provided  | Must submit compliant report and hazard log. |
| C1.2.5 | Name, profession, and registration of Clinical Safety Officer (CSO). | Free Text  | Must have a named, suitably qualified clinician as CSO. |

### C2 - Data Protection

Compliance with UK GDPR and relevant legislation.

| Code | Question | Options | Scoring Criteria (To Pass) |
| :--- | :--- | :--- | :--- |
| C2.1 | Compliant with annual DSPT assessment? | Confirmed \| Unable \| No access  | Must achieve "Standards Met" or "Exceeded". |
| C2.2 | Processes personal data (including deceased)? | Yes \| No  | If Yes, must complete subsequent questions. |
| C2.2.1 | Evidence of ICO registration. | Provided \| Not provided  | Submit evidence of current registration. |
| C2.2.2 | Attach Data Protection Impact Assessment (DPIA). | Provided \| Not provided  | Must provide a DPIA with sufficient detail. |
| C2.2.3 | Copy/link to transparency information (Privacy Notice). | Provided \| Not provided  | Must demonstrate materials are available to the buyer. |
| C2.2.4 | Product terms and conditions / EULA. | Provided \| Not provided  | Terms must be clear and fair regarding privacy. |
| C2.2.5 | Location of data storage/processing. | UK only \| Outside UK  | |
| C2.2.6 | If outside UK, set out compliance arrangements. | Free text  | Must confirm adequacy status or use IDTAs. |

### C3 - Technical Security

Meeting industry best practice security standards.

| Code | Question | Options | Scoring Criteria (To Pass) |
| :--- | :--- | :--- | :--- |
| C3.1 | Attach Cyber Essentials Certificate. | Provided \| Not Provided  | Must have a valid certificate (valid for 12 months). |
| C3.2 | Signed the Cyber Security Charter for NHS Suppliers? | Yes \| No  | If Yes, skip remaining C3 questions. |
| C3.3 | Summary report of external penetration test (last 12 months). | Provided \| Not provided  | Must show no vulnerabilities scoring 7.0+ (CVSS). |
| C3.4 | Adherence to DSIT/NCSC Software Security Code of Practice. | Confirmed \| Unable  | Must confirm alignment to the code. |
| C3.5 | Plan for implementing Multi-Factor Authentication (MFA). | Yes \| No  | Must confirm a plan is in place. |
| C3.5.1 | MFA enabled for supplier privileged access? | Yes \| No \| N/A  | Must confirm MFA for all privileged/remote access. |
| C3.6 | Logging and reporting requirements defined. | Yes \| No  | Must confirm audit trails/logging are in place. |

### C4 - Interoperability Criteria

Establishing how well the product exchanges data.

| Code | Question | Options | Scoring Criteria (To Pass) |
| :--- | :--- | :--- | :--- |
| C4.1 | Does the product expose any APIs? | Yes \| No  | |
| C4.1.1 | Do APIs use international/industry standards? | Free text  | List and justify standards used. |
| C4.1.2 | Do APIs follow GDS Open API Best Practice? | Confirm \| Cannot  | Must confirm or complete C4.1.3. |
| C4.1.3 | Basis on which APIs are made available to third parties. | Free Text  | Set out the approach for third-party integration. |
| C4.2 | Intended to share/receive data from national/local systems? | Yes \| No  | |
| C4.2.1 | Capable of using NHS number to identify patient data? | Yes \| No  | Must answer yes or set out alternative. |
| C4.2.2 | Integrate with NHS PDS or local record systems? | Yes \| No  | Must answer yes or set out alternative. |
| C4.2.3 | Approach to identify records if "No" to above. | Free Text  | Set out how data accuracy is maintained. |
| C4.2.4 | Use NHS login to verify identity (if patient-facing)? | Yes \| No \| N/A  | Answer yes or set out measures in C4.2.6. |
| C4.2.5 | Support DAPB3051 for public health/social care? | Yes \| No \| N/A  | If applicable, answer must be yes. |
| C4.2.6 | Approach to authenticating user (if not using NHS login). | Free Text  | Must ensure user privacy is protected. |

---

## D. Key Principles for Success

### D1 - Usability and Accessibility

This section provides a comparative indication and is not a pass/fail assessment.

| Code | Question | Options | Supporting Information |
| :--- | :--- | :--- | :--- |
| D1.1 | Info on how product fits into existing care pathways. | Provided \| Not provided  | Provide user journeys or instructions. |
| D1.2 | Testing with intended users to validate usability. | Yes \| No  | |
| D1.3 | Considered Accessible Information Standard. | Confirm \| Cannot  | Regarding compliance with Equalities Act (2010). |
| D1.4 | Is your product a web or mobile application? | Yes \| No  | |
| D1.4.1 | Comply with WCAG 2.2 AA or higher? | Yes \| Plan \| No \| N/A  | UK Gov policy requires AA or higher. |
| D1.4.2 | Timescale to obtain WCAG 2.2 AA. | Free Text  | Only if "Plan in place" was selected above. |
| D1.4.3 | Link to published accessibility statement. | Free text  | |
| D1.5 | Average service availability (past 12 months). | Free text  | Percentage to two decimal places. |

---

## Supporting Documentation Checklist

Ensure documents are labelled with company name, question number, and date.

* **A11** - CQC Report
* **B4** - User journeys and data flows
* **C1.1** - Pre-Acquisition Questionnaire (PAQ) Form
* **C1.2.3** - Clinical Safety Case Report
* **C1.3.4** - Hazard Log
* **C2.2.1** - Information Commissioner's registration
* **C2.2.2** - Data Protection Impact Assessment (DPIA)
* **C2.2.4** - Terms and Conditions / EULA
* **C3.1** - Cyber Essentials Certification
* **C3.2** - External Penetration Test Summary Report
* **D1.1** - User Journeys / Care Pathway integration
