---
title: "Tabletop Exercise (TTX) Action & Implementation Log"
category: dspt-7-continuity
---

# Tabletop Exercise (TTX) Action & Implementation Log

**Exercise Date:** November 14, 2025
**Review Date:** December 20, 2025
**Participants:** {{ cto_name }} (SIRO), {{ siro_name }} (CTO)

## Issue and Action Tracking

| Issue Identified | Action Required | Owner | Deadline | Status | Completion Date | Verification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Delay in Credential Retrieval:** Emergency 'unseal' keys took 15 mins to locate during the simulated Vault outage. | Create a centralized physical 'Break-Glass' folder in a secure, fireproof location. | CTO | 30/11/25 | **Complete** | 25/11/25 | Physical inspection by SIRO. |
| **Notification Clarity:** The draft email to NHS Trusts was deemed too technical for non-IT clinical staff. | Create a 'Plain English' incident template for Clinical Safety Officers. | SIRO | 05/12/25 | **Complete** | 01/12/25 | Template added to Incident Plan v2.0. |
| **MFA Redundancy:** Scenario showed that if the CTO's primary phone is lost, Northflank access is delayed. | Provision and test a secondary hardware security key (YubiKey) for Northflank/AWS. | CTO | 15/12/25 | **Complete** | 10/12/25 | Successful test login recorded in audit log. |
| **Contact Data Currency:** Two emergency contact emails for the pilot Trust were found to be out of date. | Conduct a full audit of the Customer Emergency Contact Registry. | SIRO | 20/12/25 | **Complete** | 18/12/25 | Verified contact list uploaded to secure vault. |

## Board Sign-off

We confirm that the actions identified during the November 2025 Business Continuity Exercise have been implemented within the defined timescales to ensure the resilience of the {{ platform_name }} service.

**Signed:** {{ cto_name }}, SIRO)  **Date:** 28/12/2025
