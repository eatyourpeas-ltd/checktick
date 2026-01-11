---
title: "Data & Records Management Policy"
category: dspt-1-confidential-data
---

# Data & Records Management Policy

**Version:** 1.0
**Board Approved:** [Date]
**Review Date:** [Date + 1 Year]
**Policy Lead:** {{ siro_name }} (SIRO)

## 1. Purpose

This policy defines {{ platform_name }}’s commitment to managing data as a critical asset, ensuring compliance with the UK GDPR and the NHS Records Management Code of Practice.

## 2. Information Lifecycle Management

### 2.1 Collection & Accuracy (Data Quality)

* Data is collected only for specified, explicit, and legitimate clinical/research purposes.
* Accuracy is enforced via Django form validation and database-level constraints.

### 2.2 Secure Storage

* All data is stored in the UK/EEA (Northflank/AWS).
* **Encryption at Rest:** All health data is encrypted using AES-256-GCM.
* **Encryption in Transit:** Minimum TLS 1.2 is enforced for all connections.

### 2.3 Access & Tracking

* Access is granted based on the **Principle of Least Privilege**.
* All access to patient data is recorded in the **Audit Log**, including the identity of the actor, timestamp, and action performed.

### 2.4 Data Transfer

* No patient data is to be transferred via unencrypted channels (e.g., email).
* Secure data exports are only available to authorized 'Organization Owners' or 'Data Custodians' via authenticated HTTPS sessions.

## 3. Retention & Disposal Schedule

{{ platform_name }} enforces data minimization. We do not keep data "just in case."

| Data Category | Retention Period | Action at Expiry |
| :--- | :--- | :--- |
| **Active Survey Data** | Duration of survey + 6 months | Permanent Hard Delete |
| **User Account Data** | Duration of active subscription | Account Deactivation |
| **Audit Logs** | 7 Years | Secure Archival Purge |
| **Consent Records** | 10 Years | Automated Deletion |

### 3.1 Disposal Method

* Disposal is performed via **Cryptographic Erasure**. When a survey or record is deleted, the associated encryption keys and database rows are purged. This makes recovery of the data impossible.

## 4. Legal Holds

The SIRO may place a 'Legal Hold' on any record set subject to ongoing litigation or a specific request from a healthcare trust. This overrides the automated deletion schedule.

## 5. Roles & Responsibilities

* **SIRO:** Final accountability for the Data Policy.
* **CTO:** Responsible for the technical implementation of encryption and deletion logic.
* **Staff:** Responsible for ensuring local copies of exported data are managed according to Trust-specific local policies.
