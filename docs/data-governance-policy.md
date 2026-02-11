---
title: Data Protection Policy
category: None
---

**Version:** 1.0
**Last Updated:** {{ site.updated_date | default: "Please update in admin settings" }}
**Review Date:** {{ site.policy_review_date | default: "Annual review required" }}

This policy explains how {{ site.organisation_name | default: "your organisation" }} handles personal and sensitive data collected through CheckTick surveys, in compliance with data protection laws.

---

## 1. Introduction

### 1.1 Purpose

This policy sets out how we:

- Collect, use, and protect survey data
- Ensure compliance with data protection laws
- Respect the rights of survey participants
- Define responsibilities for data handling

### 1.2 Scope

This policy applies to:

- All survey data collected through CheckTick
- All users with access to CheckTick (survey creators, editors, viewers, organisation administrators)
- Personal data, sensitive personal data, and anonymous data
- Data throughout its lifecycle (collection, storage, use, deletion)

### 1.3 Legal Basis

This policy complies with:

- **UK GDPR** - Data Protection Act 2018
- **EU GDPR** - Regulation (EU) 2016/679 (if applicable)
- **NHS Data Security and Protection Toolkit** (for NHS organisations)
- **Caldicott Principles** (for health and social care data)
- **Common Law Duty of Confidentiality**

---

## 2. Data Controller Information

### 2.1 Data Controller

The data controller for survey data is:

**Organisation:** {{ site.organisation_name | default: "Your Organisation Name" }}
**Address:** {{ site.organisation_address | default: "Your Organisation Address" }}
**Email:** {{ site.data_controller_email | default: site.admin_email | default: "dpo@example.org" }}
**Phone:** {{ site.organisation_phone | default: "Your Organisation Phone" }}

### 2.2 Data Protection Officer (DPO)

If your organisation is required to appoint a DPO:

**Name:** {{ site.dpo_name | default: "To be appointed" }}
**Email:** {{ site.dpo_email | default: site.data_controller_email | default: "dpo@example.org" }}
**Phone:** {{ site.dpo_phone | default: "Contact via email" }}

**When to contact the DPO:**

- Questions about data protection rights
- Concerns about data handling
- Data breach notifications
- Subject access requests
- Complaints about data processing

### 2.3 Information Governance Lead

For operational data governance questions:

**Name:** {{ site.ig_lead_name | default: "Contact organisation administrator" }}
**Email:** {{ site.ig_lead_email | default: site.admin_email | default: "admin@example.org" }}
**Phone:** {{ site.ig_lead_phone | default: "Contact via email" }}

---

## 3. Data Protection Principles

We process data in accordance with the following principles (GDPR Article 5):

### 3.1 Lawfulness, Fairness, and Transparency

We will:

- Process data lawfully with appropriate legal basis
- Be transparent about what data we collect and why
- Inform participants how their data will be used
- Not use data in ways participants wouldn't reasonably expect

### 3.2 Purpose Limitation

We will:

- Collect data for specific, explicit, and legitimate purposes
- Not use data in ways incompatible with those purposes
- Clearly state the purpose when creating surveys
- Obtain new consent if purpose changes significantly

### 3.3 Data Minimization

We will:

- Collect only data that is necessary for the stated purpose
- Not collect data "just in case" it might be useful
- Design surveys to minimize personal data collection
- Use anonymization and pseudonymization where possible

### 3.4 Accuracy

We will:

- Take reasonable steps to ensure data is accurate
- Allow participants to correct their responses (where appropriate)
- Update or delete inaccurate data when identified
- Provide mechanisms for data quality checks

### 3.5 Storage Limitation

We will:

- Keep data only as long as necessary for the stated purpose
- Implement automatic deletion after retention periods expire
- Provide warnings before deletion
- Securely delete data when no longer needed

**Default retention period:** 6 months after survey closure
**Maximum retention period:** 24 months after survey closure
**See:** [Data Retention Policy](/docs/data-governance-retention/)

### 3.6 Integrity and Confidentiality

We will:

- Implement appropriate technical and organisational security measures
- Protect data from unauthorized access, loss, or damage
- Encrypt data in transit and at rest
- Limit access to authorized personnel only
- Audit all data access

**See:** [Data Security Guide](/docs/data-governance-security/)

### 3.7 Accountability

We will:


- Demonstrate compliance with data protection principles
- Maintain records of processing activities
- Conduct Data Protection Impact Assessments (DPIAs) when required
- Regularly review and update policies
- Train staff on data protection responsibilities

---

## 4. Lawful Basis for Processing

### 4.1 Legal Bases

We process data under one or more of the following legal bases (GDPR Article 6):

**1. Consent (Article 6(1)(a))**

- Participants provide explicit, informed consent
- Used for most surveys collecting personal data
- Consent can be withdrawn at any time

**2. Legal Obligation (Article 6(1)(c))**

- Processing necessary to comply with legal requirements
- e.g., statutory audits, mandatory reporting

**3. Public Task (Article 6(1)(e))**

- Processing necessary for tasks in the public interest
- e.g., public health monitoring, service improvement

**4. Legitimate Interests (Article 6(1)(f))**

- Processing necessary for legitimate interests
- Balanced against participants' rights and interests
- Not used for sensitive personal data

### 4.2 Special Category Data

For sensitive personal data (health, race, religion, etc.), we use (GDPR Article 9):

**1. Explicit Consent (Article 9(2)(a))**

- Clear, specific consent for processing sensitive data

**2. Public Health (Article 9(2)(h) & (i))**

- Processing necessary for public health purposes
- Health/social care provision
- Conducted under duty of confidentiality

**3. Research (Article 9(2)(j))**

- Processing necessary for research in public interest
- Subject to appropriate safeguards

---

## 5. Data Subject Rights

Participants have the following rights under GDPR:

### 5.1 Right to Be Informed

Participants must be informed:

- What data is collected
- Why it's collected
- How it will be used
- Who will have access
- How long it will be kept
- Their rights

**Implementation:** Privacy notice shown before survey

### 5.2 Right of Access

Participants can request:

- Confirmation that we process their data
- Copy of their data
- Information about processing

**How to request:** Contact organisation administrator
**Response time:** Within 30 days
**Cost:** Free (unless excessive/repeated requests)

### 5.3 Right to Rectification

Participants can request:

- Correction of inaccurate data
- Completion of incomplete data

**Implementation:** Contact organisation administrator
**Response time:** Within 30 days

### 5.4 Right to Erasure ("Right to be Forgotten")

Participants can request deletion if:

- Data no longer necessary
- Consent is withdrawn
- Data processed unlawfully
- Legal obligation to delete

**Exceptions:**

- Legal claims/proceedings
- Public interest in health
- Research in public interest (with safeguards)

**Implementation:** Contact organisation administrator
**Response time:** Within 30 days

### 5.5 Right to Restrict Processing

Participants can request restriction if:

- Accuracy is contested
- Processing is unlawful (but they don't want deletion)
- We no longer need the data, but they need it for legal claims
- They've objected to processing (pending verification)

**Implementation:** Data marked as restricted, not deleted
**Response time:** Within 30 days

### 5.6 Right to Data Portability

Participants can request:

- Their data in machine-readable format (CSV, JSON)
- Transfer to another organisation (where feasible)

**Applies when:**

- Processing based on consent or contract
- Processing is automated

**Implementation:** Download survey responses
**Response time:** Within 30 days

### 5.7 Right to Object

Participants can object to processing based on:

- Legitimate interests
- Public interest
- Research purposes

**Implementation:** Case-by-case assessment
**Response time:** Within 30 days

### 5.8 Rights Related to Automated Decision Making

**Not applicable** - CheckTick does not perform automated decision-making or profiling.

---

## 6. Roles and Responsibilities

### 6.1 Data Controller

**Responsibilities:**

- Ensure compliance with data protection laws
- Approve high-risk processing activities
- Respond to regulatory inquiries
- Maintain accountability documentation

**Who:** Organisation administrator or designated role

### 6.2 Data Protection Officer (DPO)

**Responsibilities:**

- Advise on data protection compliance
- Monitor compliance with policy
- Conduct DPIAs and audits
- Liaise with regulatory authorities
- Handle data subject requests and complaints

**Who:** As appointed by organisation (if required)

### 6.3 Survey Creators

**Responsibilities:**

- Design surveys with data minimization in mind
- Provide clear privacy notices
- Choose appropriate legal basis
- Close surveys when data collection complete
- Download and securely store data if needed
- Delete data when no longer needed

**Access:** Can download their own survey data

### 6.4 Organisation Owners

**Responsibilities:**

- Oversee data governance for all surveys
- Assign data custodians as needed
- Review and extend retention periods
- Manage legal holds
- Respond to data subject requests
- Investigate data breaches

**Access:** Can download all survey data in organisation

### 6.5 Data Custodians

**Responsibilities:**

- Securely store and manage assigned survey data
- Follow data security best practices
- Report data breaches immediately
- Delete data when instructed

**Access:** Can download data from assigned surveys only

### 6.6 Editors and Viewers

**Responsibilities:**

- Edit survey structure only (editors)
- No access to response data
- Report suspected breaches

**Access:** Cannot download survey data

---

## 7. Security Measures

### 7.1 Technical Measures

We implement:

**Encryption:**

- Data encrypted in transit (TLS 1.3)
- Data encrypted at rest (AES-256)
- Database encryption

**Access Control:**

- Role-based access control (RBAC)
- Multi-factor authentication (recommended)
- Password policies (minimum 12 characters)

**Audit Logging:**

- All data access logged
- Download history maintained
- Regular audit reviews

**Backup and Recovery:**

- Regular automated backups
- Encrypted backups
- Disaster recovery procedures

**See:** [Data Security Guide](/docs/data-governance-security/)

### 7.2 Organisational Measures

We implement:

**Policies and Procedures:**

- This data protection policy
- Data breach response plan
- Access control procedures
- Retention and deletion schedules

**Training:**

- Mandatory data protection training
- Role-specific training
- Regular refresher training

**Audits:**

- Regular compliance audits
- Penetration testing
- Vulnerability assessments

**Vendor Management:**

- Data processing agreements with third parties
- Vendor security assessments
- Regular reviews

---

## 8. Data Sharing

### 8.1 Internal Sharing

Data may be shared within the organisation with:

- Organisation administrators
- Survey creators (their own surveys)
- Data custodians (assigned surveys)

**Conditions:**

- Role-based access only
- Legitimate need to know
- Logged and auditable

### 8.2 External Sharing

Data may be shared externally only when:

- Legal obligation requires it
- Participant has consented
- Necessary for public health
- Anonymized/aggregated (not personal data)

**Safeguards:**

- Data sharing agreement in place
- Minimum necessary data shared
- Secure transfer methods
- Recipient security assessment

### 8.3 International Transfers

If data is transferred outside UK/EU:

- Adequate level of protection ensured
- Appropriate safeguards in place (e.g., Standard Contractual Clauses)
- Documented and approved

**Current:** CheckTick data stored in {{ site.data_location | default: "UK/EU" }}

---

## 9. Data Breach Management

### 9.1 Definition

A data breach is any incident that compromises the confidentiality, integrity, or availability of personal data.

**Examples:**

- Unauthorized access
- Accidental disclosure
- Loss or theft of devices
- Ransomware/malware
- Improper disposal

### 9.2 Reporting Internally

**Any breach must be reported immediately:**

1. **Report to organisation administrator** (within 1 hour)
2. **Report to DPO** (within 1 hour, if applicable)
3. **Provide details:**
   - What happened
   - When it happened
   - What data was affected
   - Potential impact
   - Actions taken

**See:** [Data Security Guide - Breach Response](/docs/data-governance-security/#data-breach-response)

### 9.3 Reporting to Authorities

If breach likely to result in risk to rights and freedoms:

**Report to ICO (or relevant authority):**

- Within 72 hours of becoming aware
- Include details of breach and mitigation
- Ongoing updates as investigation proceeds

**Our DPO/administrator will handle regulatory reporting.**

### 9.4 Notifying Individuals

If breach likely to result in high risk to individuals:

**Notify affected individuals:**

- Without undue delay
- In clear, plain language
- Describe nature of breach
- Provide contact point for information
- Describe likely consequences
- Recommend protective measures

---

## 10. Data Protection Impact Assessments (DPIAs)

### 10.1 When Required

We conduct DPIAs for:

- New types of data collection
- Large-scale processing of special category data
- Systematic monitoring
- Automated decision-making
- Processing vulnerable individuals' data

### 10.2 DPIA Process

1. Describe processing activity
2. Assess necessity and proportionality
3. Identify risks to individuals
4. Evaluate risk severity and likelihood
5. Identify mitigation measures
6. Approve or reject processing
7. Review and update regularly

### 10.3 Consultation

DPIAs are reviewed by:

- Data Protection Officer
- Organisation administrator
- Relevant stakeholders
- ICO (if high risk remains after mitigation)

---

## 11. Retention and Deletion

### 11.1 Retention Periods

**Survey Responses:**

- Default: 6 months after survey closure
- Maximum: 24 months after survey closure
- Extensions require justification

**Audit Logs:**

- Retained for 6 years (regulatory requirement)
- Anonymized after 2 years

**Backup Data:**

- Included in main retention periods
- Purged when main data deleted

**See:** [Data Retention Policy](/docs/data-governance-retention/)

### 11.2 Deletion Process

**Soft Deletion:**

- Survey data marked deleted
- 30-day grace period for recovery
- Not visible to users

**Hard Deletion:**

- After 30 days, permanent deletion
- All backups purged
- Cannot be recovered
- Deletion logged

### 11.3 Legal Holds

Processing may be extended beyond retention periods for:

- Legal proceedings
- Regulatory investigations
- Formal complaints

**Legal holds:**

- Applied by organisation owner only
- Require documented justification
- Reviewed every 6 months
- Lifted when no longer needed

---

## 12. Training and Awareness

### 12.1 Mandatory Training

All users must complete:

- Data protection awareness training (annually)
- Role-specific training (on appointment)
- CheckTick-specific training (before first use)

### 12.2 Training Content

**Awareness Training Covers:**

- Data protection principles
- Legal obligations
- Individual rights
- Security best practices
- Breach reporting

**Role-Specific Training:**

- Survey creators: Privacy by design, consent
- Data custodians: Secure data handling
- Organisation owners: Compliance oversight

### 12.3 Refresher Training

- Annual refresher required
- Policy updates communicated immediately
- New regulations incorporated

---

## 13. Monitoring and Review

### 13.1 Policy Review

This policy is reviewed:

- Annually (minimum)
- When regulations change
- After significant data breaches
- When new processing activities introduced

**Next review:** {{ site.policy_review_date | default: "Set in admin settings" }}

### 13.2 Compliance Monitoring

We monitor compliance through:

- Quarterly access audits
- Annual security assessments
- Data protection impact assessments
- User training records
- Incident reports

### 13.3 Metrics

We track:

- Number of surveys with personal data
- Data subject requests (type, response time)
- Data breaches (number, severity)
- Training completion rates
- Retention period extensions

---

## 14. Contact and Complaints

### 14.1 General Inquiries

For questions about this policy or data protection:

**Email:** {{ site.data_controller_email | default: site.admin_email | default: "dpo@example.org" }}
**Phone:** {{ site.organisation_phone | default: "Contact via email" }}
**Post:** {{ site.organisation_address | default: "Your Organisation Address" }}

### 14.2 Data Subject Requests

To exercise your rights (access, rectification, erasure, etc.):

**Email:** {{ site.dpo_email | default: site.data_controller_email | default: "dpo@example.org" }}
**Subject Line:** "Data Subject Request - [Your Name]"
**Include:** Full name, contact details, description of request

**Response time:** Within 30 days

### 14.3 Complaints

If you are not satisfied with how we handle your data:

**Internal Complaint:**

- Contact our DPO/administrator (details above)
- We will investigate and respond within 30 days

**External Complaint:**

- You have the right to complain to the supervisory authority:

**Information Commissioner's Office (ICO):**
Website: https://ico.org.uk/
Phone: 0303 123 1113
Post: Information Commissioner's Office, Wycliffe House, Water Lane, Wilmslow, Cheshire, SK9 5AF

---

## 15. Related Documentation

**User Guides:**

- [Data Governance Overview](/docs/data-governance-overview/)
- [Data Export Guide](/docs/data-governance-export/)
- [Data Retention Policy](/docs/data-governance-retention/)
- [Data Security Guide](/docs/data-governance-security/)
- [Special Cases Guide](/docs/data-governance-special-cases/)

**Technical Documentation:**

- [Implementation Guide](/docs/data-governance-implementation/)
- [API Documentation](/docs/api/)

**External References:**

- [UK GDPR Guidance (ICO)](https://ico.org.uk/for-organisations/guide-to-data-protection/guide-to-the-general-data-protection-regulation-gdpr/)
- [NHS Data Security and Protection Toolkit](https://www.dsptoolkit.nhs.uk/)
- [Caldicott Principles](https://www.gov.uk/government/publications/the-caldicott-principles)

---

## Document Control

**Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | {{ site.updated_date \| default: "YYYY-MM-DD" }} | {{ site.ig_lead_name \| default: "Name" }} | Initial policy |

**Approval:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Data Controller | {{ site.organisation_owner \| default: "Name" }} | _________________ | ________ |
| DPO (if applicable) | {{ site.dpo_name \| default: "Name" }} | _________________ | ________ |

**Distribution:**

- All CheckTick users (via system notification)
- Organisation website
- Staff handbook
- New user onboarding

---

**This policy is effective from:** {{ site.policy_effective_date | default: "Date of publication" }}

**Note:** Fields marked with `{{ }}` should be configured in CheckTick admin settings or organisation profile.
