---
title: "Incident Reporting & Escalation Procedure"
category: dspt-6-incidents
---

# Incident Reporting & Escalation Procedure

**Version:** 2.0 (DSPT Compliant)
**Owner:** SIRO ({{ siro_name }})
**Technical Lead:** CTO ({{ cto_name }})

## 1. Internal Reporting & Triage

Any team member who discovers a potential security breach, lost device, or suspicious activity must notify the **CTO and SIRO** via the emergency Slack channel (#security-war-room) or direct phone call within **1 hour**.

* **Triage:** The CTO will immediately assess the "Confidentiality, Integrity, and Availability" (CIA) impact to determine if the event is a 'Near-Miss' or a 'Confirmed Incident.'

## 2. External Reporting & Deadlines

{{ platform_name }} adheres to strict regulatory and contractual reporting windows:

| Stakeholder | Deadline | Trigger |
| :--- | :--- | :--- |
| **Healthcare Customers (Trusts)** | **Within 24 Hours** | Any incident affecting the development, hosting, or data of the software. |
| **DSPT / ICO** | **Within 72 Hours** | Any incident likely to result in a risk to the rights and freedoms of individuals. |
| **Police (Action Fraud)** | **Immediate** | Cases of theft, extortion (ransomware), or targeted fraud. |

## 3. Communication Protocol

* **Customer Alerts:** Initial notification to Trusts will be sent by the SIRO via email to the registered Data Protection Officer (DPO) and Clinical Lead.
* **DSPT Reporting:** Reports will be submitted via the [DSPT Incident Reporting Tool](https://www.dsptoolkit.nhs.uk/Incidents).

## 4. Post-Incident Review & RCA

For every incident or significant near-miss, a formal review is mandatory:

1. **Incident Log:** The event is recorded in `compliance/incident-log.csv`.
2. **Five Whys Analysis:** The CTO conducts a Root Cause Analysis (RCA) to identify the systemic failure (Technical, Procedural, or Human).
3. **Prevention:** Corrective actions are implemented and verified within 30 days to prevent a "Repeat Incident."

## 5. Annual Review

This procedure is tested annually through a "Tabletop Exercise" where the team simulates a data breach to verify that these reporting windows can be met.
