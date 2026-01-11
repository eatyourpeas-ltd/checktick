---
title: "Incident Response Plan & Data Breach Policy"
category: dspt-6-incidents
---

# Incident Response Plan & Data Breach Policy

**Version:** 1.0
**Last Reviewed:** [Insert Date post-July 1, 2025]
**SIRO:** {{ siro_name }} | **Cyber Lead:** {{ cto_name }}

## 1. Definition of an Incident

An incident is any event that threatens the confidentiality, integrity, or availability of {{ platform_name }} data or services. This includes:

* **Cyber Security Incidents:** Malware, Ransomware, DDoS, or unauthorized DB access.
* **Physical Incidents:** Loss/theft of a staff laptop.
* **Data Breaches:** Accidental or unlawful destruction, loss, or disclosure of personal data.

## 2. Immediate Response Steps (The "4-Hour" Window)

1. **Identify & Contain:** {{ cto_name }} isolates the affected system (e.g., revoking API keys, shutting down a Northflank service, or remote-wiping a laptop).
2. **Assess:** Determine what data was involved. Is it "Special Category" (health) data?
3. **Notify SIRO:** {{ cto_name }} briefs {{ siro_name }} on the technical scope.

## 3. Notification Requirements

### 3.1 To the ICO

If the breach is likely to result in a risk to the rights and freedoms of individuals, {{ siro_name }} must report it to the **ICO** within **72 hours** of becoming aware.

### 3.2 To the Data Controller (Our Customers)

As a Data Processor, {{ platform_name }} has a legal obligation under GDPR to notify our customers (the Healthcare Orgs) **without undue delay** if their survey data is compromised.

### 3.3 To the DSPT (Data Security On-Line Reporting)

If the incident meets the "Severity" threshold (e.g., affecting >150 individuals or clinical safety), it must be reported via the **DSPT Incident Reporting Tool**.

## 4. Triage Levels

| Level | Description | Action |
| :--- | :--- | :--- |
| **P1 (Critical)** | Data breach involving health data or total system outage. | Immediate containment; 72hr ICO clock starts. |
| **P2 (High)** | Suspicious activity detected; account compromise without data leak. | Password resets; MFA audit; notify affected user. |
| **P3 (Normal)** | Localized bug or hardware failure with no data risk. | Standard patch/repair process. |

## 5. Post-Incident Review

Within 5 business days of any P1 or P2 incident, the team will:

* Identify the root cause.
* Update the **Vulnerability Management Policy** if required.
* Update the **Asset Register** or **Data Flow Map** if the incident revealed new risks.

## 6. Root Cause Analysis (RCA) Procedure

Following the resolution of any 'Medium' or 'High' severity incident, an RCA meeting must be held within 5 working days.

### 6.1 The 'Five Whys' Framework

We investigate beyond the immediate technical failure:

1. **The Symptom:** (e.g., An API endpoint was accessible without a token).
2. **The Immediate Cause:** (e.g., A permission decorator was missing from the view).
3. **The Root Cause:** (e.g., A new developer didn't know about the custom decorator).
4. **The Process Failure:** (e.g., The peer review checklist didn't include a 'permissions check').
5. **The Systemic Fix:** (e.g., Implement an automated test that 'scans' all views for decorators).

### 6.2 Implementation of Findings

* **Policy Update:** If the failure was human, we update the Staff Security Agreement or Training.
* **Technical Patch:** If the failure was code-based, we deploy a fix within 24 hours.
* **Regression Testing:** A new automated test case is *always* added to our RBAC test suite to ensure the vulnerability can never be re-introduced by future code changes.

## 7. Post-Incident Governance & Board Oversight

### 7.1 The Post-Incident Action Plan

Every reportable breach requires a formal Action Plan containing:

1. **Remediation:** Technical fixes to close the vulnerability.
2. **Communication:** Plan for notifying affected subjects/Trusts.
3. **Prevention:** Process changes to prevent recurrence.

### 7.2 Escalation Matrix

We manage overdue security actions with a zero-tolerance approach:

* **Level 1 (Target Date):** Action owner (CTO or SIRO) updates the status in the Spot Check Log.
* **Level 2 (Target Date + 48hrs):** If an action is missed, it is flagged as 'Overdue' and reviewed in an ad-hoc session.
* **Level 3 (Escalation):** Persistent delays are recorded as a 'Governance Failure' in the Risk Register, requiring a formal board-level reassessment of the product's live status.

### 7.3 Board Assurance

The SIRO retains final sign-off authority. No incident is marked as 'Closed' until the Board is satisfied that all items in the Action Plan have been verified as complete via technical testing or policy audit.

## 8. Data Subject Notification (High Risk Breaches)

In accordance with UK GDPR, if a breach is likely to result in a 'high risk' to the rights and freedoms of individuals (e.g., identity theft, fraud, or sensitive clinical data exposure), the following steps apply:

### 8.1 The Notification Threshold

The SIRO will determine if notification is required. 'High risk' is generally assumed if:

* Unencrypted health data/clinical survey responses are accessed by unauthorized parties.
* Encryption keys are compromised alongside the database.

### 8.2 Content of the Notice

The notification must be sent directly to the individual (via email or post) and contain:

1. **Description:** What happened and when.
2. **Data Involved:** What specific categories of their data were affected.
3. **Protective Steps:** What {{ platform_name }} has done to stop the breach and what the individual should do (e.g., change passwords).
4. **Assistance:** Direct contact details for our support team for further queries.

### 8.3 Trust Coordination

As a SaaS provider, we will act in accordance with our **Data Processing Agreement (DPA)**. We will notify the Controller (the NHS Trust) immediately and support them in their duty to inform the data subjects.

## 9. Post-Incident Review (PIR) & Root Cause Analysis

Every incident or significant near-miss must be followed by a PIR within 5 working days of resolution.

### 9.1 Root Cause Analysis (RCA)

We use the 'Five Whys' method to ensure we aren't just fixing symptoms.

* **Target:** Identify if the failure was Technical (e.g., code bug), Procedural (e.g., missing check), or Human (e.g., training gap).
* **Output:** A formal RCA report is stored in the Incident Log.

### 9.2 Prevention of Repeat Incidents

To ensure a vulnerability is not re-exploited:

1. **Corrective Action:** Immediate fix (e.g., patching the library).
2. **Preventative Action:** Systemic fix (e.g., adding automated vulnerability scanning to the CI/CD pipeline).
3. **Follow-up Audit:** The SIRO will re-verify the fix 3 months post-incident. If the same vulnerability is identified elsewhere, it is escalated as a 'Major Governance Failure.'

### 9.3 Lessons Learned Sharing

Anonymized summaries of incidents and lessons learned are a standing agenda item for our Quarterly Governance Meetings to ensure both directors remain aware of the threat landscape.
